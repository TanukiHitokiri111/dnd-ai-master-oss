"""Character API: CRUD персонажа."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user
from app.models import CharacterUpdate, CharacterListResponse

from app.api.v1.character_helpers import _get_char, _get_items, _row_to_char
from app.api.v1.world_catalog import visible_class_names
from app.knowledge.worlds import resolve_class_key

router = APIRouter(tags=["characters"])

@router.get("/characters", response_model=CharacterListResponse)
async def list_characters(user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM characters WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
        )
        rows = await cursor.fetchall()
        chars = []
        for row in rows:
            r = dict(row)
            items = await _get_items(db, r["id"])
            chars.append(_row_to_char(r, items))
        return {"characters": chars}
    finally:
        await db.close()


@router.get("/characters/{char_id}")
async def get_character(char_id: str, user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)
        items = await _get_items(db, char_id)
        return _row_to_char(char, items)
    finally:
        await db.close()


@router.get("/characters/{char_id}/multiclass-classes")
async def get_multiclass_classes(char_id: str, user_id: str = Depends(get_current_user)):
    """Классы, доступные персонажу для мультикласса, в его текущем мире.

    Возвращает имена-ключи (plain для стандартных миров, суффиксированные
    вида «Солдат__modern_earth» для миров с алиасами) — именно их бэкенд
    ожидает в level-up (new_class) и валидирует через resolve_class_key.
    Исключает классы, которые персонаж уже взял.
    """
    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)
        # Мир персонажа из game_state.current_world ('' если записи нет).
        cursor = await db.execute(
            "SELECT current_world FROM game_state WHERE character_id = ?", (char_id,)
        )
        gs_row = await cursor.fetchone()
        if gs_row:
            try:
                world = (gs_row["current_world"] or "") if "current_world" in gs_row.keys() else ""
            except (IndexError, KeyError):
                world = ""
        else:
            world = ""

        # Уже взятые классы: основной (characters.class_name) + мультиклассы (character_classes)
        owned = {char["class_name"]}
        cursor = await db.execute(
            "SELECT class_name FROM character_classes WHERE character_id = ?", (char_id,)
        )
        for row in await cursor.fetchall():
            owned.add(row["class_name"])

        # Мир: список классов мира (или None → все неэксклюзивные классы)
        allowed = visible_class_names(world)

        result = []
        for name in allowed:
            key = resolve_class_key(world, name)
            if key not in owned and name not in owned:
                result.append(key)
        return {"classes": result}
    finally:
        await db.close()


@router.put("/characters/{char_id}")
async def update_character(
    char_id: str,
    data: CharacterUpdate,
    user_id: str = Depends(get_current_user),
):
    db = await get_db()
    try:
        _ = await _get_char(db, char_id, user_id)  # проверка существования
        updates = data.model_dump(exclude_unset=True)

        # JSON-поля
        for field in ("stats", "features", "proficiencies", "skill_proficiencies", "languages"):
            if field in updates and updates[field] is not None:
                updates[field] = json.dumps(updates[field])

        if updates:
            # Санитизируем ключи: только допустимые имена полей
            ALLOWED_COLS = {
                "name", "race", "class_name", "background_name", "subclass", "subrace",
                "stats", "speed", "features", "proficiencies", "skill_proficiencies",
                "languages", "backstory", "mixed_heritage", "is_dead", "hp_current",
            }
            safe_updates = {k: v for k, v in updates.items() if k in ALLOWED_COLS}
            if safe_updates:
                set_clause = ", ".join(f"{k} = ?" for k in safe_updates)
                values = list(safe_updates.values()) + [char_id]
                await db.execute(
                    f"UPDATE characters SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                    values,
                )
                await db.commit()

        row = await db.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
        items = await _get_items(db, char_id)
        return _row_to_char(dict(await row.fetchone()), items)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.delete("/characters/{char_id}", status_code=204)
async def delete_character(char_id: str, user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        # Проверяем что персонаж принадлежит пользователю (is_dead не блокирует удаление)
        char = await _get_char(db, char_id, user_id)

        # Атомарно: все DELETE в одной транзакции (обрыв не оставит orphan-записи)
        await db.execute("BEGIN IMMEDIATE")
        # ── Полная очистка хвостов персонажа ──
        # История, мем-палас, инвентарь
        await db.execute("DELETE FROM chat_history WHERE character_id = ? AND user_id = ?", (char_id, user_id))
        await db.execute("DELETE FROM user_memory WHERE character_id = ? AND user_id = ?", (char_id, user_id))
        await db.execute("DELETE FROM items WHERE character_id = ?", (char_id,))
        # Способности, классы, квесты, заклинания
        await db.execute("DELETE FROM character_spells WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM character_classes WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM quests WHERE character_id = ?", (char_id,))
        # Мир/состояние, NPC, компаньоны, внешность
        await db.execute("DELETE FROM game_state WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM npcs WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM npc_appearance WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM companions WHERE character_id = ?", (char_id,))
        # Промпт-лог (диагностика)
        await db.execute("DELETE FROM prompt_log WHERE character_id = ?", (char_id,))
        # Мультиплеер: выкинуть из сессий и удалить его сообщения
        await db.execute("DELETE FROM session_members WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM game_messages WHERE character_id = ?", (char_id,))
        await db.execute("DELETE FROM group_chat_history WHERE character_id = ?", (char_id,))

        # Файл портрета (внешность), если есть
        appearance_url = char.get("appearance_url") if isinstance(char, dict) else (char.appearance_url if hasattr(char, "appearance_url") else None)
        # Файл портрета НЕ удаляем: картинка остаётся в общем пуле image_assets
        # и переиспользуется другими персонажами/игроками (см. image_assets).

        cursor = await db.execute(
            "DELETE FROM characters WHERE id = ? AND user_id = ?", (char_id, user_id)
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, detail="Персонаж не найден")
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# ──────────────────────────────────────────────
# INVENTORY CRUD
# ──────────────────────────────────────────────

