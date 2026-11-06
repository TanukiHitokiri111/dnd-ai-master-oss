"""Character API: повышение уровня."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_db
from app.deps import get_current_user
from app.knowledge.srd_rules import CLASS_HIT_DIE, MULTICLASS_PROFICIENCIES, check_level_up
from app.models import LevelUpRequest, LevelUpResult
from app.services.level_up_service import (
    validate_multiclass,
    get_features_for_level,
    get_hit_points,
    apply_stat_increase,
    compute_spell_slots,
)

from app.api.v1.character_helpers import _get_char

router = APIRouter(tags=["characters"])


def _resolve_target_class(new_class: str, current: str) -> str:
    """new_class как есть, если это валидный ключ; иначе title()-нормализация.

    Точный ключ приоритетнее .title(): суффиксированные ключи миров
    («Пси-навигатор__deep_space») .title() искажает.
    """
    if new_class in CLASS_HIT_DIE:
        return new_class
    return new_class.title() if new_class != current else current


def _build_class_map(existing: list, row) -> dict:
    """class_map из строк БД; при пустом списке — строка из characters (level 1)."""
    if not existing:
        stored_name = row["class_name"]
        # точный ключ приоритетнее .title(): суффиксированные ключи миров
        # («Пси-навигатор__deep_space») .title() искажает
        existing = [{"class_name": stored_name, "level": row["level"],
                     "hit_die": CLASS_HIT_DIE.get(stored_name)
                     or CLASS_HIT_DIE.get(stored_name.title(), 8),
                     "subclass": row.get("subclass", "")}]
    return {c["class_name"]: dict(c) for c in existing}


def _stats_of(row) -> dict:
    """stats из строки characters: JSON-строка или уже dict."""
    raw = row["stats"]
    return json.loads(raw) if isinstance(raw, str) else raw


async def _ensure_class_row(db, char_id: str, class_map: dict, target_class: str, row) -> dict:
    """Мультикласс: валидация + INSERT новой строки класса. Возвращает profs.

    Вызывается когда target_class ещё не в class_map (новый класс персонажа).
    """
    ok, err = validate_multiclass(_stats_of(row), target_class)
    if not ok:
        raise HTTPException(400, detail=f"Мультикласс невозможен: {err}")
    mc_profs = MULTICLASS_PROFICIENCIES.get(
        target_class, {"armor": [], "weapons": [], "tools": [], "skills": [], "saves": []}
    )
    hit_die = CLASS_HIT_DIE.get(target_class, 8)
    await db.execute(
        "INSERT INTO character_classes (character_id, class_name, level, hit_die) VALUES (?,?,1,?)",
        (char_id, target_class, hit_die),
    )
    class_map[target_class] = {"class_name": target_class, "level": 0, "hit_die": hit_die, "subclass": ""}
    return mc_profs


def _asi_class_levels(target_class: str) -> set[int]:
    """Уровни класса, дающие ASI (Воин/Плут получают дополнительные)."""
    levels = {4, 8, 12, 16, 19}
    if target_class == "Воин":
        levels.update((6, 14))
    elif target_class == "Плут":
        levels.add(10)
    return levels


async def _apply_stat_increase(db, char_id: str, row, data, new_level: int, target_class: str) -> dict | None:
    """ASI на уровнях класса 4/8/... (не персонажа — мультикласс-семантика)."""
    if new_level not in _asi_class_levels(target_class) or not data.stat_increase:
        return None
    new_stats = apply_stat_increase(_stats_of(row), data.stat_increase)
    await db.execute(
        "UPDATE characters SET stats=? WHERE id=?",
        (json.dumps(new_stats, ensure_ascii=False), char_id),
    )
    return data.stat_increase


def _normalize_profs(mc_profs: dict) -> dict:
    """Нормализация: skills может быть int (кол-во на выбор) → list[str]."""
    norm_profs = dict(mc_profs)
    if isinstance(norm_profs.get("skills"), int):
        n = norm_profs["skills"]
        norm_profs["skills"] = [f"{n} навык(ов) на выбор"] if n > 0 else []
    return norm_profs


def _classes_out(class_map: dict, target_class: str, new_level: int) -> list[dict]:
    """Список классов для LevelUpResult: target_class уже с новым уровнем."""
    return [
        {"class_name": cn, "level": new_level if cn == target_class else cd["level"],
         "hit_die": cd["hit_die"], "subclass": cd.get("subclass", "")}
        for cn, cd in class_map.items()
    ]


@router.post("/characters/{char_id}/level-up")
async def level_up(
    char_id: str,
    data: LevelUpRequest,
    user_id: str = Depends(get_current_user),
):
    """Повысить уровень персонажа. Поддерживает мультикласс.

    Драйвер: делегирует шаги декомпозированным хелперам модуля.
    """
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await _get_char(db, char_id, user_id)

        if not check_level_up(row["level"], row["xp"]):
            await db.rollback()
            raise HTTPException(400, detail="Недостаточно опыта для повышения уровня")

        cursor = await db.execute(
            "SELECT class_name, level, hit_die, subclass FROM character_classes WHERE character_id=?",
            (char_id,),
        )
        class_map = _build_class_map(await cursor.fetchall(), row)
        target_class = _resolve_target_class(data.new_class or row["class_name"], row["class_name"])
        mc_profs: dict = {"armor": [], "weapons": [], "tools": [], "skills": [], "saves": []}

        if target_class not in class_map:
            mc_profs = await _ensure_class_row(db, char_id, class_map, target_class, row)

        old_level = class_map[target_class]["level"]
        new_level = old_level + 1
        hit_die = class_map[target_class]["hit_die"]
        await db.execute(
            "UPDATE character_classes SET level=? WHERE character_id=? AND class_name=?",
            (new_level, char_id, target_class),
        )
        class_map[target_class]["level"] = new_level

        total_level = sum(c["level"] for c in class_map.values())
        await db.execute("UPDATE characters SET level=? WHERE id=?", (total_level, char_id))
        hp_gained = get_hit_points(hit_die, data.hp_roll)
        new_hp_max = row["hp_max"] + hp_gained

        stat_increases_applied = await _apply_stat_increase(
            db, char_id, row, data, new_level, target_class
        )

        await db.execute(
            "UPDATE characters SET hp_max=?, hp_current=? WHERE id=?",
            (new_hp_max, new_hp_max, char_id),
        )
        features_gained = get_features_for_level(target_class, new_level)
        classes_for_slots = [(c["class_name"], c["level"]) for c in class_map.values()]
        spell_slots = compute_spell_slots(classes_for_slots)
        await db.commit()

        # ── Очки умений: +3 за каждое повышение уровня (очки копятся) ──
        # Начисление НЕ должно ломать level-up ни при каких обстоятельствах:
        # все исключения (включая ImportError сервиса) глотаем молча.
        ability_points_gained = 0
        ability_points_total = None
        try:
            from app.services.ability_service import ensure_ability_schema  # ленивый импорт
            await ensure_ability_schema(db)  # колонка characters.ability_points точно есть
            await db.execute(
                "UPDATE characters SET ability_points = COALESCE(ability_points, 0) + 3 WHERE id = ?",
                (char_id,),
            )
            await db.commit()
            cur = await db.execute(
                "SELECT COALESCE(ability_points, 0) FROM characters WHERE id = ? LIMIT 1",
                (char_id,),
            )
            pts_row = await cur.fetchone()
            ability_points_gained = 3
            if pts_row and pts_row[0] is not None:
                ability_points_total = int(pts_row[0])
        except Exception:
            pass

        result = LevelUpResult(
            character_id=char_id, total_level=total_level, classes=_classes_out(class_map, target_class, new_level),
            hp_gained=hp_gained, hp_max_new=new_hp_max, features_gained=features_gained,
            proficiencies_gained=_normalize_profs(mc_profs), spell_slots=spell_slots,
            stat_increases_applied=stat_increases_applied,
            more_levels=check_level_up(total_level, row["xp"]),
        )
        # app/models/levelup.py не трогаем: новые ключи добавляем в dict-ответ
        # (сериализация существующих полей идентична прежнему контракту).
        payload = result.model_dump()
        payload["ability_points_gained"] = ability_points_gained
        payload["ability_points_total"] = ability_points_total
        return payload
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()



# ─── ABILITIES (очки умений) ─────────────────────────────


class AbilityAllocation(BaseModel):
    ability_key: str
    ranks: int


class AllocateAbilitiesRequest(BaseModel):
    class_key: str
    allocations: list[AbilityAllocation]


async def _class_rows(db, char_id: str) -> list[tuple[str, int]]:
    """[(class_name, level)] из character_classes; [] если таблицы/строк нет."""
    try:
        cursor = await db.execute(
            "SELECT class_name, level FROM character_classes WHERE character_id=? ORDER BY rowid",
            (char_id,),
        )
        return [(str(r["class_name"]), int(r["level"] or 0)) for r in await cursor.fetchall()]
    except Exception:
        return []


def _resolve_class_level(class_rows: list[tuple[str, int]], row: dict, class_key: str | None) -> tuple[str, int]:
    """(класс, уровень в нём) для системы умений.

    class_key из запроса приоритетнее; иначе первый класс из character_classes,
    иначе characters.class_name (total level как fallback — для одноклассовых
    персонажей он совпадает с уровнем класса).
    """
    if class_key:
        for name, lvl in class_rows:
            if name == class_key:
                return name, lvl
        return class_key, (class_rows[0][1] if class_rows else int(row.get("level", 1) or 1))
    if class_rows:
        return class_rows[0]
    return row["class_name"], int(row.get("level", 1) or 1)


def _ability_error() -> dict:
    return {
        "points": 0, "learned": [], "available": [], "next": [],
        "error": "сервис умений недоступен",
    }


async def _abilities_state(db, char_id: str, row: dict, class_key: str | None = None) -> dict:
    """Общее состояние системы умений (для GET /abilities и POST allocate).

    Ленивый импорт ability_service: файл создаётся параллельно и может
    отсутствовать — тогда возвращаем заглушку с error (код 200).
    """
    try:
        from app.services.ability_service import (
            compute_visible,
            get_ability_points,
            get_learned,
        )
    except ImportError:
        return _ability_error()

    try:
        cls_name, cls_level = _resolve_class_level(await _class_rows(db, char_id), row, class_key)
        # learned: {ability_key: rank} из character_abilities
        learned = await get_learned(db, char_id)
        points = await get_ability_points(db, char_id)
        visible = compute_visible(cls_name, cls_level, learned)
    except Exception:
        return _ability_error()
    if not isinstance(visible, dict):
        return _ability_error()
    visible.setdefault("points", int(points or 0))
    return visible


@router.get("/characters/{char_id}/abilities")
async def get_abilities(
    char_id: str,
    user_id: str = Depends(get_current_user),
):
    """Состояние системы очков умений: накопленные очки и видимая сетка умений."""
    db = await get_db()
    try:
        row = await _get_char(db, char_id, user_id)
        return await _abilities_state(db, char_id, row)
    finally:
        await db.close()


@router.post("/characters/{char_id}/abilities/allocate")
async def allocate_abilities(
    char_id: str,
    data: AllocateAbilitiesRequest,
    user_id: str = Depends(get_current_user),
):
    """Вложить накопленные очки в умения. Очки КОПЯТСЯ — тратить можно в любой момент."""
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await _get_char(db, char_id, user_id)

        try:
            from app.services.ability_service import (
                apply_allocation,
                get_learned,
                get_ability_points,
                validate_allocation,
            )
        except ImportError:
            await db.rollback()
            raise HTTPException(503, detail="сервис умений недоступен")

        try:
            cls_name, cls_level = _resolve_class_level(await _class_rows(db, char_id), row, data.class_key)
            learned = await get_learned(db, char_id)
            points = await get_ability_points(db, char_id)

            allocs = [{"ability_key": a.ability_key, "ranks": a.ranks} for a in data.allocations]
            ok, err = validate_allocation(cls_name, cls_level, learned, points, allocs)
            if not ok:
                await db.rollback()
                raise HTTPException(400, detail=err or "некорректное распределение очков")

            await apply_allocation(db, char_id, cls_name, allocs)
            # apply_allocation коммитит сам; при неудаче компенсируем роллбэком
            try:
                if db.in_transaction:
                    await db.commit()
            except (AttributeError, TypeError):
                pass
        except HTTPException:
            raise
        except Exception:
            await db.rollback()
            raise

        return await _abilities_state(db, char_id, row, class_key=data.class_key or None)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.get("/characters/{char_id}/abilities/{ability_key}")
async def get_ability_detail(
    char_id: str,
    ability_key: str,
    user_id: str = Depends(get_current_user),
):
    """Полное описание умения со всеми 5 рангами (для просмотра игроком)."""
    db = await get_db()
    try:
        row = await _get_char(db, char_id, user_id)
        try:
            from app.services.ability_service import (
                _full_entry,
                get_learned,
                load_class_abilities,
            )
        except ImportError:
            raise HTTPException(503, detail="сервис умений недоступен")

        cls_name, cls_level = _resolve_class_level(await _class_rows(db, char_id), row, None)
        abilities = load_class_abilities(cls_name)

        ab = next(
            (a for a in abilities if isinstance(a, dict) and a.get("key") == ability_key), None
        )
        if ab is None:
            raise HTTPException(404, detail="Умение не найдено")

        # Ранг персонажа — из character_abilities (get_learned), не из каталога
        rank = int((await get_learned(db, char_id)).get(ability_key, 0) or 0)
        entry = _full_entry(ab, rank)
        return {
            "key": entry.get("key", ability_key),
            "name": entry.get("name", ability_key),
            "desc": entry.get("desc", ""),
            "unlock_level": entry.get("unlock_level", 1),
            "type": entry.get("type", ""),
            "stat": entry.get("stat", ""),
            "rank": rank,
            "max_rank": entry.get("max_rank", 5),
            "ranks": entry.get("ranks") or [{"rank": r, "desc": entry.get("desc", "")} for r in range(1, 6)],
            "prereq": list(entry.get("prereq") or []),
            "learned": rank >= 1,
        }
    finally:
        await db.close()


# ─── QUESTS ─────────────────────────────────────────────
