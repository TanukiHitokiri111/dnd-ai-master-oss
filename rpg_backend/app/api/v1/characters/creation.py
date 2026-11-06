"""Character API: создание персонажа."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import new_id
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.knowledge.srd_rules import BACKGROUNDS, CLASS_STARTING_EQUIPMENT, RACIAL_TRAITS, RACIAL_SUBRACES, RACE_STAT_BONUSES, CLASS_FEATURES_L1, CLASS_PROFICIENCIES, CLASS_HIT_DIE, SPELLS_BY_CLASS, CASTER_CLASSES, SPELL_SLOTS_BY_LEVEL, CLASS_SPELL_LIMITS, SUBCLASS_OPTIONS
from app.knowledge.loot_tables import get_backstory_items
from app.knowledge.worlds import WORLD_TEMPLATES, get_world_races, get_world_classes, resolve_race_key, resolve_class_key
from app.models import CharacterCreate, CharacterStats, CharacterBackstory, CharacterCreationResult

from app.api.v1.character_helpers import _ai_review_backstory, _build_starting_inventory, _casting_ability_for_class, _compute_ac, _get_char, _get_items, _parse_dm_changes, _resolve_item, _row_to_char
from app.api.v1.characters.creation_steps import (
    apply_stat_bonuses,
    build_backgrounds,
    canonize_class,
    canonize_race,
    check_world_availability,
    collect_racial_traits,
    match_subclass,
    resolve_world,
)

router = APIRouter(tags=["characters"])

# ── Мировые предыстории (world_backgrounds.json) ──
_WORLD_BACKGROUNDS_PATH = "/app/data/world_backgrounds.json"


def _world_background_names(world_key: str) -> set[str]:
    """Имена всех мировых предысторий для world_key (по всем расам).

    Безопасно: если файла нет / ключа мира нет / JSON битый — пустой set,
    валидация тогда идёт только по стандартному BACKGROUNDS.
    """
    if not world_key:
        return set()
    try:
        with open(_WORLD_BACKGROUNDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    world_bg = data.get(world_key)
    if not isinstance(world_bg, dict):
        return set()
    names: set[str] = set()
    for race_bgs in world_bg.values():
        if not isinstance(race_bgs, list):
            continue
        for bg in race_bgs:
            if isinstance(bg, dict):
                name = bg.get("name")
                if name:
                    names.add(name)
    return names


@router.post("/characters/create", status_code=201)
async def create_character(
    data: CharacterCreate,
    user_id: str = Depends(get_current_user),
):
    """Шаг 1: подписка + валидация мира/расы/класса + сборка справочников."""
    # Проверка активной подписки (только в платном режиме)
    if settings.require_access:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or not int(row[0]):
                raise HTTPException(403, detail="Нет активного доступа.")
        finally:
            await db.close()

    # Мир — определяем до валидации расы/класса
    world_key = resolve_world(data.world)

    # Канонизация расы и класса с учётом мира
    race_name = canonize_race(world_key, data.race)
    class_name = canonize_class(world_key, data.class_name)

    # Проверка доступности в мире
    check_world_availability(world_key, race_name, class_name, data.race, data.class_name)

    # Расовые черты (раса + подраса + смешанное наследие) — через канонизированный ключ
    racial, subrace_name, subrace_data = collect_racial_traits(data, race_name)

    # Классовые умения L1 + подкласс
    class_feats, subclass_features, subclass_data = match_subclass(class_name, data.subclass)

    # Владения
    profs = CLASS_PROFICIENCIES.get(class_name, {})

    # Стартовое снаряжение
    starting_eq = CLASS_STARTING_EQUIPMENT.get(class_name, {})

    # Хит-дайс → базовые ПЗ
    hit_die = CLASS_HIT_DIE.get(class_name, 8)
    hp_max = hit_die  # уровень 1 = максимум кубика

    # Стандартные статы (27 point buy было бы круто, но пока стандартный набор)
    # + применяем стат-бонусы расы, подрасы и унаследованных подрас
    actual_stats = apply_stat_bonuses(data, race_name, subrace_data)

    # Предыстории
    backgrounds = build_backgrounds()

    # Создаём запись персонажа в БД
    char_id = new_id()
    db = await get_db()
    try:
        # Проверим что пользователь зарегистрирован
        cur = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not await cur.fetchone():
            raise HTTPException(status_code=401, detail="Пользователь не найден — зарегистрируйтесь")
        # Сохраняем mixed_heritage в БД
        mixed_json = json.dumps(data.mixed_heritage, ensure_ascii=False) if data.mixed_heritage else '{}'

        await db.execute(
            """INSERT INTO characters (id, user_id, name, race, class_name, background_name, subclass, subrace, level, xp,
               stats, hp_max, hp_current, ac, init_ac, speed, features, proficiencies,
               skill_proficiencies, languages, backstory, mixed_heritage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, 10, 10, 30, '[]', '{}', '[]', '[]', '', ?)""",
            (char_id, user_id, data.name, race_name, class_name, data.background_name, data.subclass, subrace_name,
             json.dumps(actual_stats, ensure_ascii=False), hp_max, hp_max, mixed_json),
        )

        # Создаём game_state с выбранным миром
        world_info = WORLD_TEMPLATES[world_key]
        await db.execute(
            """INSERT INTO game_state (user_id, character_id, current_world, location, scene, weapon, phase, last_reply, nsfw_level, nsfw_last_styles, updated_at)
               VALUES (?, ?, ?, ?, '', '', 'exploration', '', 'on', '[]', datetime('now'))
               ON CONFLICT(user_id, character_id) DO UPDATE SET
               current_world=excluded.current_world,
               location=excluded.location,
               updated_at=datetime('now')""",
            (user_id, char_id, world_key, world_info.name),
        )

        await db.commit()
    finally:
        await db.close()

    # Заклинания для кастеров
    available_spells = SPELLS_BY_CLASS.get(class_name, []) if class_name in CASTER_CLASSES else []
    spell_slots = SPELL_SLOTS_BY_LEVEL.get(1, {}) if class_name in CASTER_CLASSES else {}
    is_caster = class_name in CASTER_CLASSES

    return {
        "id": char_id,
        "name": data.name,
        "race": race_name,
        "class_name": class_name,
        "level": 1,
        "hp_max": hp_max,
        "hp_current": hp_max,
        "racial_traits": racial,
        "class_features": class_feats,
        "proficiencies": profs,
        "skill_choices": profs.get("skills_choices", {}),
        "hit_die": hit_die,
        "hp_max_suggested": hp_max,
        "stats_suggested": actual_stats,
        "starting_equipment": starting_eq,
        "backgrounds": backgrounds,
        "is_caster": is_caster,
        "available_spells": available_spells,
        "spell_slots": spell_slots,
        "spell_limits": CLASS_SPELL_LIMITS.get(class_name, {"cantrips": 0, "level1": 0}),
        "casting_ability": _casting_ability_for_class(class_name),
        "subclass": data.subclass,
        "subrace": subrace_name,
        "subraces_available": RACIAL_SUBRACES.get(race_name),
        "subrace_key": data.subrace,
        "subclass_options": SUBCLASS_OPTIONS.get(class_name),
        "mixed_heritage": data.mixed_heritage,
        "world": world_key,
        "world_name": world_info.name,
    }


# ──────────────────────────────────────────────
# STEP 2: Сохранить финальные статы и навыки
# ──────────────────────────────────────────────

@router.post("/characters/{char_id}/stats")
async def set_character_stats(
    char_id: str,
    data: CharacterStats,
    user_id: str = Depends(get_current_user),
):
    """Шаг 2. Игрок распределил статы, выбрал навыки и языки."""
    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)  # проверка существования

        # Сохраняем статы и навыки
        stats_json = json.dumps(data.stats)
        skills_json = json.dumps(data.skill_proficiencies)
        langs_json = json.dumps(data.languages)

        await db.execute(
            "UPDATE characters SET stats=?, skill_proficiencies=?, languages=?, updated_at=datetime('now') WHERE id=?",
            (stats_json, skills_json, langs_json, char_id),
        )
        await db.commit()

        # Если кастер — возвращаем доступные заклинания
        class_name = char["class_name"]
        available_spells = SPELLS_BY_CLASS.get(class_name, []) if class_name in CASTER_CLASSES else []
        spell_slots = SPELL_SLOTS_BY_LEVEL.get(1, {}) if class_name in CASTER_CLASSES else {}

        return {
            "ok": True,
            "stats": data.stats,
            "skill_proficiencies": data.skill_proficiencies,
            "languages": data.languages,
            "is_caster": class_name in CASTER_CLASSES,
            "available_spells": available_spells,
            "spell_slots": spell_slots,
            "spell_limits": CLASS_SPELL_LIMITS.get(class_name, {"cantrips": 0, "level1": 0}),
            "casting_ability": _casting_ability_for_class(class_name),
        }
    finally:
        await db.close()


# ──────────────────────────────────────────────
# STEP 3: Предыстория + AI-ревью + финал персонажа
# ──────────────────────────────────────────────

@router.post("/characters/{char_id}/finalize", response_model=CharacterCreationResult)
async def finalize_character(
    char_id: str,
    data: CharacterBackstory,
    background_name: str = "",
    user_id: str = Depends(get_current_user),
):
    """
    Шаг 3. Игрок пишет предысторию. AI-мастер:
    - анализирует и может скорректировать статы
    - добавляет/убирает предметы из стартового инвентаря
    - добавляет расовые черты и классовые умения
    - выдаёт финальный инвентарь
    """

    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)

        # Мир персонажа из game_state.current_world ('' если записи нет)
        gs_cursor = await db.execute(
            "SELECT current_world FROM game_state WHERE character_id = ?", (char_id,)
        )
        gs_row = await gs_cursor.fetchone()
        char_world = (gs_row["current_world"] or "") if gs_row and "current_world" in gs_row.keys() else ""

        # Валидация background_name: стандартная D&D ИЛИ мировая предыстория мира персонажа
        if background_name and background_name not in BACKGROUNDS and background_name not in _world_background_names(char_world):
            await db.close()
            raise HTTPException(400, detail=f"Неизвестная предыстория: {background_name}")

        race_name = char["race"]
        class_name = char["class_name"]
        stats = json.loads(char["stats"]) if isinstance(char["stats"], str) else char["stats"]

        # Расовые черты
        racial = RACIAL_TRAITS.get(race_name, [])

        # Классовые умения
        class_feats = list(CLASS_FEATURES_L1.get(class_name, []))

        # Подкласс (загружаем из БД)
        subclass_key = char.get("subclass", "")
        subclass_features = []
        subclass_data = None
        if subclass_key:
            subclass_options = SUBCLASS_OPTIONS.get(class_name, {})
            for opt in subclass_options.get("options", []):
                if opt["key"] == subclass_key:
                    subclass_data = opt
                    subclass_features = opt["features"]
                    class_feats = class_feats + [{
                        "name": f"{subclass_options['label']}: {opt['name']}",
                        "desc": opt["desc"],
                        "flavor": subclass_options.get("flavor", "")
                    }] + opt["features"]
                    break

        # Владения
        profs = CLASS_PROFICIENCIES.get(class_name, {})
        profs_json = json.dumps(profs)

        # AI-ревью предыстории
        dm_notes = ""
        adjusted_stats = dict(stats)
        final_items = []
        final_features = list(class_feats)

        if data.backstory.strip():
            dm_notes = await _ai_review_backstory(
                data.backstory, char["name"], race_name, class_name,
                stats, class_feats, racial,
            )
            # TOCTOU-фикс (аудит r10/03): после долгого AI-вызова перечитываем
            # персонажа — параллельный PUT /characters/{char_id} мог обновить
            # stats; дельты мастера должны лечь на СВЕЖИЕ данные.
            char = await _get_char(db, char_id, user_id)
            stats = json.loads(char["stats"]) if isinstance(char["stats"], str) else char["stats"]
            # Парсим заметки мастера на предмет изменений
            adjusted_stats, extra_items, extra_features = _parse_dm_changes(
                dm_notes, stats
            )
            final_features.extend(extra_features)

            # Собираем полный инвентарь
            # Добавляем предметы из текста предыстории
            if data.backstory.strip():
                bs_items = get_backstory_items(data.backstory, class_name)
                extra_items.extend(bs_items)
            final_items = _build_starting_inventory(
                class_name, background_name, extra_items, stats, adjusted_stats
            )
        else:
            final_items = _build_starting_inventory(class_name, background_name, [], stats, adjusted_stats)

        # Вычисляем КД
        ac = _compute_ac(adjusted_stats, final_items, class_name)

        # Сохраняем персонажа полностью
        con_mod = (adjusted_stats.get("con", 10) - 10) // 2
        hp_max = max(1, CLASS_HIT_DIE.get(class_name, 8) + con_mod)
        features_json = json.dumps(final_features)

        # Транзакция: character UPDATE + items DELETE/INSERT атомарно
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                """UPDATE characters SET
                   stats=?, backstory=?, background_name=?, features=?, proficiencies=?,
                   hp_max=?, hp_current=?, ac=?, init_ac=?, updated_at=datetime('now')
                   WHERE id=?""",
                (
                    json.dumps(adjusted_stats), data.backstory, background_name,
                    features_json, profs_json,
                    hp_max, hp_max, ac, ac, char_id,
                ),
            )

            # Очищаем старые предметы и вставляем новые
            await db.execute("DELETE FROM items WHERE character_id = ?", (char_id,))
            for item in final_items:
                resolved = _resolve_item(item.get("item_key", ""))
                import json as _json
                await db.execute(
                    """INSERT INTO items (character_id, item_key, item_name, item_type, item_subtype, qty, slot, equipped, attunement, notes, modifiers, flavor)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        char_id,
                        item.get("item_key", ""),
                        item.get("item_name", resolved["item_name"]),
                        item.get("item_type", resolved["item_type"]),
                        item.get("item_subtype", resolved["item_subtype"]),
                        item.get("qty", 1),
                        item.get("slot", resolved["slot"]),
                        item.get("equipped", 0),
                        item.get("attunement", 0),
                        item.get("notes", ""),
                        _json.dumps(item.get("modifiers", {}), ensure_ascii=False),
                        item.get("flavor") or resolved.get("flavor", ""),
                    ),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        # Загружаем финальный результат
        items = await _get_items(db, char_id)
        row = await db.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
        char_final = _row_to_char(dict(await row.fetchone()), items)

        return CharacterCreationResult(
            character=char_final,
            dm_notes=dm_notes,
            starting_items=items,
            features=final_features,
            racial_traits=racial,
            subclass=subclass_key,
            subclass_features=subclass_features,
        )

    finally:
        await db.close()


# ──────────────────────────────────────────────
# CRUD: список / один / обновить / удалить
# ──────────────────────────────────────────────

