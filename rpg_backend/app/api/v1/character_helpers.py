"""Хелперы для Character API: валидация, вычисления, парсинг."""

import json
import random
import re

from fastapi import HTTPException
from app.db import get_db
from app.knowledge.srd_rules import (
    BACKGROUNDS, CLASS_STARTING_EQUIPMENT, ITEM_CATALOG, XP_THRESHOLDS, check_level_up,
    SPELL_FLAVOR,
)
from app.knowledge.item_utils import EXTRA_ITEM_CATALOG, RUS_ITEM_KEY_MAP, resolve_item as _resolve_item
from app.models import CharacterStats
from app.knowledge.loot_tables import generate_modifiers


# ── _delete_owned_row ──
async def _delete_owned_row(
    char_id: str,
    user_id: str,
    sql: str,
    params: tuple,
    *,
    not_found: str,
) -> None:
    """Общий DELETE owned-row эндпоинта: проверка владельца + DELETE + 404.

    Используется inventory.py (remove_item/remove_spell) и crud.py.
    """
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)
        cursor = await db.execute(sql, params)
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, detail=not_found)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# ── _ai_review_backstory ──

async def _ai_review_backstory(
    backstory: str, name: str, race: str, class_name: str,
    stats: dict, features: list, racial: list,
) -> str:
    """AI-мастер анализирует предысторию и даёт заметки."""
    import asyncio
    from openai import AsyncOpenAI
    from app.config import settings, POLZA_EXTRA_BODY
    from app.logger import logger

    client = AsyncOpenAI(
        base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.api_timeout,
    )

    prompt = f"""Ты — мастер D&D 5e. Игрок создал персонажа и написал предысторию.

**Персонаж:**
- Имя: {name}
- Раса: {race}
- Класс: {class_name}
- Характеристики: {json.dumps(stats, ensure_ascii=False)}
- Классовые умения: {json.dumps([f['name'] for f in features], ensure_ascii=False)}
- Расовые черты: {json.dumps([r['name'] for r in racial], ensure_ascii=False)}

**Предыстория игрока:**
{backstory}

Проанализируй предысторию и напиши заметки мастера (от 2-го лица, к игроку на «ты»):
1. Если предыстория противоречит статам — предложи скорректировать (например, «Твой персонаж — кузнец, но СИЛ 8. Предлагаю СИЛ 14.»)
2. Если из истории следует предмет, которого нет в стартовом снаряжении — добавь его.
   Формат добавления предмета: [ITEM: ключ_предмета]
   Примеры ключей: [ITEM: smith_hammer] или [ITEM: heirloom_ring] или [ITEM: sea_chart]
   НЕ используй в скобках текст «item_key» — только конкретный ключ латиницей.
3. Если персонажу подходят дополнительные навыки — предложи.
4. Похвали интересные моменты.

Ответь кратко, по делу, 3-5 предложений."""

    last_error = None
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=settings.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
                extra_body=POLZA_EXTRA_BODY,
            )
            return resp.choices[0].message.content or getattr(resp.choices[0].message, "reasoning_content", None) or ""
        except Exception as e:
            last_error = e
            logger.warning(f"AI backstory review attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2.0 * (attempt + 1))

    logger.error("AI backstory review all retries exhausted: %s", last_error, exc_info=True)
    return "*Мастер кивнул, прочитав твою историю.*"


# ── _build_starting_inventory ──

def _norm_item(raw: dict) -> dict:
    """Нормализовать предмет: ключи/дефолты."""
    d = dict(raw)
    if "item" in d and "item_key" not in d:
        d["item_key"] = d.pop("item")
    d.setdefault("item_key", "")
    d.setdefault("qty", 1)
    d.setdefault("equipped", 0)
    d.setdefault("notes", "")
    d.setdefault("modifiers", {})
    d.setdefault("flavor", "")
    return d


def _cat_of(key: str) -> dict:
    """Каталог предмета по ключу."""
    return ITEM_CATALOG.get(key) or EXTRA_ITEM_CATALOG.get(key) or {}


def _class_starting_items(class_name: str) -> list[dict]:
    """Стартовые предметы класса: список имён или choices/always."""
    items: list[dict] = []
    class_eq = CLASS_STARTING_EQUIPMENT.get(class_name, {})
    if isinstance(class_eq, list):
        for name in class_eq:
            mapped_key = RUS_ITEM_KEY_MAP.get(name.lower().strip(), "")
            items.append(_norm_item({
                "name": name, "item_name": name,
                "item_key": mapped_key, "qty": 1,
                "notes": f"Стартовый предмет ({class_name})",
            }))
        return items
    for choice in class_eq.get("choices", []):
        options = choice.get("options", [])
        if options:
            item = _norm_item(random.choice(options))
            item["notes"] = f"Стартовый предмет ({class_name})"
            items.append(item)
    for item in class_eq.get("always", []):
        i = _norm_item(item)
        i["notes"] = f"Стартовый предмет ({class_name})"
        items.append(i)
    return items


def _maybe_enchant(items: list[dict]) -> None:
    """30% шанс модификаторов для оружия/брони."""
    for item in items:
        cat = _cat_of(item.get("item_key", ""))
        itype = cat.get("type", item.get("item_type", "gear"))
        if itype in ("weapon", "armor") and random.random() < 0.3:
            rarity = "uncommon"
            mods = generate_modifiers(rarity, itype)
            item["modifiers"] = {k: v for k, v in mods.items() if k not in ("flavor", "name_affix", "rarity", "prefix", "suffix")}
            item["flavor"] = mods.get("flavor", "")


def _autoequip(items: list[dict]) -> None:
    """Автоэкипировка: броня → body, оружие → main_hand / two_hands."""
    for item in items:
        cat = _cat_of(item.get("item_key", ""))
        if not cat:
            continue
        if cat["type"] == "armor" and cat["subtype"] != "shield":
            item["equipped"] = 1
            item["slot"] = "body"
        elif cat["type"] == "weapon":
            if "two_handed" in cat.get("properties", []):
                item["equipped"] = 1
                item["slot"] = "two_hands"
            elif not any(i.get("equipped") and _cat_of(i.get("item_key", "")).get("slot") == "main_hand" for i in items if i != item):
                item["equipped"] = 1
                item["slot"] = "main_hand"


def _equip_shield(items: list[dict]) -> None:
    """Щит в off_hand, если нет двуручного."""
    has_two_handed = any(
        i.get("equipped") and "two_handed" in _cat_of(i.get("item_key", "")).get("properties", [])
        for i in items
    )
    if has_two_handed:
        return
    for item in items:
        cat = _cat_of(item.get("item_key", ""))
        if cat and cat["type"] == "armor" and cat["subtype"] == "shield":
            item["equipped"] = 1
            item["slot"] = "off_hand"
            break


def _build_starting_inventory(
    class_name: str, background_name: str,
    dm_extra: list, stats: dict, adjusted_stats: dict,
) -> list[dict]:
    """Собрать стартовый инвентарь: рандом из класса + предыстория + правки мастера."""
    items: list[dict] = _class_starting_items(class_name)

    bg = BACKGROUNDS.get(background_name.title(), {})
    bg_equip = bg.get("equipment", [])
    if bg_equip:
        picked_bg = _norm_item(random.choice(bg_equip))
        picked_bg["notes"] = f"Из предыстории: {background_name}"
        items.append(picked_bg)

    for item in dm_extra:
        if not any(i["item_key"] == item.get("item_key", "") for i in items):
            items.append(item)

    # Дедупликация по item_key (пустой ключ не дедуплицируем)
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        key = item.get("item_key", "")
        if not key or key not in seen:
            seen.add(key)
            deduped.append(item)
    items = deduped

    _maybe_enchant(items)
    _autoequip(items)
    _equip_shield(items)

    return items


# ── _casting_ability_for_class ──

def _casting_ability_for_class(class_name: str) -> str:
    """Ключевая характеристика для заклинаний класса."""
    return {
        "Волшебник": "ИНТ", "Жрец": "МУД", "Друид": "МУД",
        "Бард": "ХАР", "Чародей": "ХАР", "Колдун": "ХАР",
        "Паладин": "ХАР", "Следопыт": "МУД",
    }.get(class_name, "")


# ── _compute_ac ──

def _compute_ac(stats: dict, items: list[dict], class_name: str) -> int:
    """Вычислить КД персонажа на основе экипированной брони."""
    dex_mod = (stats.get("dex", 10) - 10) // 2
    con_mod = (stats.get("con", 10) - 10) // 2
    wis_mod = (stats.get("wis", 10) - 10) // 2

    body_armor = None
    shield_equipped = False
    for item in items:
        if item.get("equipped"):
            key = item.get("item_key", "")
            cat = ITEM_CATALOG.get(key, {})
            if cat and cat.get("type") == "armor":
                if cat.get("subtype") == "shield":
                    shield_equipped = True
                else:
                    body_armor = cat

    if body_armor:
        ac = body_armor["ac_base"]
        if body_armor.get("ac_dex"):
            dex_bonus = min(dex_mod, body_armor.get("ac_dex_max", 99)) if body_armor.get("ac_dex_max") is not None else dex_mod
            ac += dex_bonus
        if shield_equipped:
            ac += 2
        return ac

    if class_name in ("Варвар",):
        ac = 10 + dex_mod + con_mod
    elif class_name in ("Монах",):
        ac = 10 + dex_mod + wis_mod
    else:
        ac = 10 + dex_mod
    if shield_equipped:
        ac += 2
    return ac


# ── _get_char ──

async def _get_char(db, char_id: str, user_id: str) -> dict:
    cursor = await db.execute(
        "SELECT * FROM characters WHERE id = ? AND user_id = ?", (char_id, user_id)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    return dict(row)


# ── _get_items ──

async def _get_items(db, char_id: str) -> list[dict]:
    cursor = await db.execute("SELECT * FROM items WHERE character_id = ?", (char_id,))
    items = []
    for r in await cursor.fetchall():
        item = dict(r)
        mods = item.get("modifiers")
        if isinstance(mods, str) and mods:
            try:
                item["modifiers"] = json.loads(mods)
            except json.JSONDecodeError:
                item["modifiers"] = {}
        elif not mods or mods == "{}":
            item["modifiers"] = {}
        items.append(item)
    return items


# ── _get_spells ──

async def _get_spells(db, char_id: str) -> list[dict]:
    cursor = await db.execute("SELECT * FROM character_spells WHERE character_id = ?", (char_id,))
    rows = []
    for r in await cursor.fetchall():
        d = dict(r)
        d["flavor"] = SPELL_FLAVOR.get(d.get("spell_key", ""), "")
        rows.append(d)
    return rows


# ── _parse_dm_changes ──

def _parse_dm_changes(dm_notes: str, original_stats: dict) -> tuple[dict, list, list]:
    """Вытащить из заметок мастера изменения статов и предметы."""
    stats = dict(original_stats)
    extra_items = []
    extra_features = []

    def _clamp_stat(val: int) -> int:
        return max(3, min(20, val))

    for m in re.finditer(r'(?:СИЛ[аыуе]?|STR)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["str"] = _clamp_stat(int(m.group(1)))
    for m in re.finditer(r'(?:ЛОВ[аыуе]?|DEX)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["dex"] = _clamp_stat(int(m.group(1)))
    for m in re.finditer(r'(?:ТЕЛ[аыуе]?|CON)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["con"] = _clamp_stat(int(m.group(1)))
    for m in re.finditer(r'(?:ИНТ[аыуе]?|INT)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["int"] = _clamp_stat(int(m.group(1)))
    for m in re.finditer(r'(?:МУД[аыуе]?|WIS)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["wis"] = _clamp_stat(int(m.group(1)))
    for m in re.finditer(r'(?:ХАР[аыуе]?|CHA)\s*[:=]?\s*(?:\w*\s+){0,3}?(?:до\s+)?(\d+)', dm_notes, re.IGNORECASE):
        stats["cha"] = _clamp_stat(int(m.group(1)))

    for m in re.finditer(r'\[ITEM:\s*(\S+)\]', dm_notes):
        item_key = m.group(1)
        resolved = _resolve_item(item_key)
        extra_items.append({**resolved, "qty": 1, "equipped": 0, "notes": "Добавлено мастером"})

    for m in re.finditer(r'\[FEAT:\s*(.+?)\]', dm_notes):
        feat_name = m.group(1).strip()
        extra_features.append({"name": feat_name, "desc": "Добавлено мастером"})

    return stats, extra_items, extra_features


# ── _row_to_char ──

def _row_to_char(row: dict, items: list[dict]) -> dict:
    """Собрать полный словарь персонажа."""
    stats = json.loads(row.get("stats", "{}")) if isinstance(row.get("stats"), str) else row.get("stats", {})
    features = json.loads(row.get("features", "[]")) if isinstance(row.get("features"), str) else row.get("features", [])
    proficiencies = json.loads(row.get("proficiencies", "{}")) if isinstance(row.get("proficiencies"), str) else row.get("proficiencies", {})
    skill_profs = json.loads(row.get("skill_proficiencies", "[]")) if isinstance(row.get("skill_proficiencies"), str) else row.get("skill_proficiencies", [])
    languages = json.loads(row.get("languages", "[]")) if isinstance(row.get("languages"), str) else row.get("languages", [])

    clean_items = []
    for it in items:
        it = dict(it)
        it["equipped"] = bool(it.get("equipped", 0))
        it["attunement"] = bool(it.get("attunement", 0))
        clean_items.append(it)

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "race": row["race"],
        "class_name": row["class_name"],
        "background_name": row.get("background_name", ""),
        "level": row["level"],
        "xp": row.get("xp", 0),
        "xp_to_next": _xp_to_next(row["level"], row.get("xp", 0)),
        "stats": stats,
        "hp_max": row["hp_max"],
        "hp_current": row["hp_current"],
        "ac": row["ac"],
        "init_ac": row.get("init_ac", row["ac"]),
        "speed": row.get("speed", 30),
        "backstory": row.get("backstory", ""),
        "subclass": row.get("subclass", ""),
        "features": features,
        "proficiencies": proficiencies,
        "skill_proficiencies": skill_profs,
        "languages": languages,
        "gold": row.get("gold", 0) or 0,
        "items": clean_items,
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at", row["created_at"]),
        "is_dead": bool(row.get("is_dead", 0)),
    }


# ── _xp_to_next ──

def _xp_to_next(level: int, xp: int) -> dict:
    """Сколько XP нужно до следующего уровня (для XP-бара в UI)."""
    cur_total = XP_THRESHOLDS.get(level)
    next_total = XP_THRESHOLDS.get(level + 1)
    if cur_total is None or next_total is None:
        return {"current": xp, "needed": None, "into": None, "span": None, "max_level": True}
    span = next_total - cur_total
    into = max(0, min(span, xp - cur_total))
    return {"current": xp, "needed": next_total, "into": into, "span": span, "max_level": False}