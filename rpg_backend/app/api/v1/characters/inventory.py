"""Character API: инвентарь, заклинания, черты."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user
from app.knowledge.srd_rules import SPELLS_BY_CLASS
from app.models import ItemCreate, ItemResponse, SpellCreate, SpellResponse, FeatureCreate

from app.api.v1.character_helpers import _get_char, _get_items, _get_spells, _resolve_item, _delete_owned_row

router = APIRouter(tags=["characters"])

@router.get("/characters/{char_id}/items", response_model=list[ItemResponse])
async def list_items(char_id: str, user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)
        items = await _get_items(db, char_id)
        return [ItemResponse(**i) for i in items]
    finally:
        await db.close()


@router.post("/characters/{char_id}/items", status_code=201)
async def add_item(
    char_id: str,
    data: ItemCreate,
    user_id: str = Depends(get_current_user),
):
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)

        # Разрезолвить предмет
        resolved = _resolve_item(data.item_key)
        name = data.item_name or resolved["item_name"]
        # Берём item_type из каталога если пользователь не переопределил (дефолт "gear" не считается)
        itype = resolved["item_type"] if data.item_type == "gear" and resolved["item_type"] != "gear" else (data.item_type or resolved["item_type"])
        isubtype = resolved["item_subtype"] if data.item_subtype == "" and resolved.get("item_subtype") else (data.item_subtype or resolved.get("item_subtype", ""))
        slot = data.slot or resolved["slot"]

        cursor = await db.execute(
            """INSERT INTO items (character_id, item_key, item_name, item_type, item_subtype, qty, slot, equipped, attunement, notes, modifiers, flavor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (char_id, data.item_key, name, itype, isubtype, data.qty, slot, int(data.equipped), int(data.attunement), data.notes,
             json.dumps({}), resolved.get("flavor", "")),
        )
        await db.commit()
        item_id = cursor.lastrowid

        row = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item = dict(await row.fetchone())
        # Преобразовать modifiers из JSON-строки
        mods = item.get("modifiers")
        if isinstance(mods, str) and mods:
            try:
                item["modifiers"] = json.loads(mods)
            except json.JSONDecodeError:
                item["modifiers"] = {}
        else:
            item["modifiers"] = {}
        return ItemResponse(**item)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.delete("/characters/{char_id}/items/{item_id}", status_code=204)
async def remove_item(char_id: str, item_id: int, user_id: str = Depends(get_current_user)):
    await _delete_owned_row(
        char_id, user_id,
        "DELETE FROM items WHERE id = ? AND character_id = ?", (item_id, char_id),
        not_found="Предмет не найден",
    )


@router.delete("/characters/{char_id}/spells/{spell_id}", status_code=204)
async def remove_spell(char_id: str, spell_id: int, user_id: str = Depends(get_current_user)):
    await _delete_owned_row(
        char_id, user_id,
        "DELETE FROM character_spells WHERE id = ? AND character_id = ?", (spell_id, char_id),
        not_found="Заклинание не найдено",
    )


# ──────────────────────────────────────────────
# SPELLS CRUD
# ──────────────────────────────────────────────


@router.get("/characters/{char_id}/spells", response_model=list[SpellResponse])
async def list_spells_for_character(char_id: str, user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)
        spells = await _get_spells(db, char_id)
        return [SpellResponse(**s) for s in spells]
    finally:
        await db.close()


@router.post("/characters/{char_id}/spells", status_code=201)
async def add_spell_to_character(
    char_id: str,
    data: SpellCreate,
    user_id: str = Depends(get_current_user),
):
    """Добавить заклинание персонажу (из SRD, кастомное, или через DM)."""
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)

        if data.spell_key:
            spell_id = await _insert_srd_spell(db, char_id, data)
        else:
            spell_id = await _insert_custom_spell(db, char_id, data)
        await db.commit()

        row = await db.execute("SELECT * FROM character_spells WHERE id = ?", (spell_id,))
        return SpellResponse(**dict(await row.fetchone()))
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


def _find_srd_spell(spell_key: str) -> dict | None:
    """Найти заклинание по ключу в каталоге SPELLS_BY_CLASS."""
    for spells in SPELLS_BY_CLASS.values():
        for s in spells:
            if s["key"] == spell_key:
                return s
    return None


async def _insert_srd_spell(db, char_id: str, data: SpellCreate) -> int:
    """Вставить SRD-заклинание (или заглушку неизвестного ключа). Возвращает id."""
    spell_info = _find_srd_spell(data.spell_key)
    if spell_info:
        cursor = await db.execute(
            """INSERT INTO character_spells (character_id, spell_key, spell_name, spell_level, school, "desc", casting_time, "range", components, duration, source, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (char_id, data.spell_key, spell_info["name"], spell_info["level"],
             spell_info["school"], spell_info["desc"], spell_info["casting_time"],
             spell_info["range"], spell_info["components"], spell_info["duration"],
             data.source or "Найдено в приключении", data.notes),
        )
    else:
        cursor = await db.execute(
            """INSERT INTO character_spells (character_id, spell_key, spell_name, spell_level, source, notes)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (char_id, data.spell_key, data.spell_key.replace("_", " ").title(),
             data.source or "Найдено в приключении", data.notes),
        )
    return cursor.lastrowid


async def _insert_custom_spell(db, char_id: str, data: SpellCreate) -> int:
    """Вставить кастомное заклинание (генерация описания при необходимости). Возвращает id."""
    import base64, os
    custom_key = f"custom_{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"

    # Генерируем описание если не дали / слишком короткое
    raw_desc = data.desc or ""
    if not raw_desc or len(raw_desc.strip()) < 20:
        from app.knowledge.srd_rules import generate_spell_desc
        desc = generate_spell_desc({
            "name": data.spell_name,
            "level": data.spell_level,
            "school": data.school or "",
            "casting_time": data.casting_time or "",
            "range": data.spell_range or "",
            "duration": data.duration or "",
        })
    else:
        desc = raw_desc

    cursor = await db.execute(
        """INSERT INTO character_spells
           (character_id, spell_key, spell_name, spell_level, school, "desc", casting_time, "range", components, duration, source, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (char_id, custom_key, data.spell_name, data.spell_level,
         data.school, desc, data.casting_time,
         data.spell_range, data.components, data.duration,
         data.source or "Создано в диалоге с DM", data.notes),
    )
    return cursor.lastrowid


# ──────────────────────────────────────────────
# FEATURES CRUD (mid-game)
# ──────────────────────────────────────────────

@router.post("/characters/{char_id}/features", status_code=201)
async def add_feature(
    char_id: str,
    data: FeatureCreate,
    user_id: str = Depends(get_current_user),
):
    """Добавить черту/умение персонажу (mid-game)."""
    import json as _json
    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)
        features = _json.loads(char["features"]) if isinstance(char["features"], str) else char["features"]
        features.append({"name": data.name, "desc": data.desc, "source": data.source})

        await db.execute(
            "UPDATE characters SET features=?, updated_at=datetime('now') WHERE id=?",
            (_json.dumps(features), char_id),
        )
        await db.commit()
        return {"ok": True, "name": data.name, "features": features}
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# ──────────────────────────────────────────────
# CHARACTER STATUS — полное окно персонажа
# ──────────────────────────────────────────────

STAT_SKILL_MAP = {
    "acrobatics": "dex", "animal_handling": "wis", "arcana": "int",
    "athletics": "str", "deception": "cha", "history": "int",
    "insight": "wis", "intimidation": "cha", "investigation": "int",
    "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int",
    "sleight_of_hand": "dex", "stealth": "dex", "survival": "wis",
}


