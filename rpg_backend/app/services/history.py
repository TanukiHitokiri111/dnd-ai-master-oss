"""Загрузка персонажа и история диалога."""

import asyncio
import json

from app.config import settings
from app.db import get_db
from app.logger import logger


async def _load_character(character_id: str) -> dict | None:
    """Загрузить персонажа из БД + предметы + заклинания (параллельно)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM characters WHERE id = ?", (character_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        r = dict(row)
        for field in ("stats", "features", "skill_proficiencies"):
            raw = r.get(field, "{}")
            try:
                r[field] = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                r[field] = {}

        # Загружаем предметы и заклинания параллельно
        async def _load_items() -> list[dict]:
            cur = await db.execute(
                "SELECT * FROM items WHERE character_id = ?", (character_id,)
            )
            return [dict(it) for it in await cur.fetchall()]

        async def _load_spells() -> list[dict]:
            try:
                cur = await db.execute(
                    "SELECT * FROM character_spells WHERE character_id = ?", (character_id,)
                )
                return [dict(s) for s in await cur.fetchall()]
            except Exception:
                return []

        items_task = asyncio.create_task(_load_items())
        spells_task = asyncio.create_task(_load_spells())
        r["items"], r["spells"] = await asyncio.gather(items_task, spells_task)

        return r
    except Exception:
        logger.exception("Failed to load character %s", character_id)
        return None
    finally:
        await db.close()


def _trim_history(history: list[dict]) -> list[dict]:
    """Обрезать историю если слишком длинная (system prompt + N последних)."""
    max_msgs = settings.max_history_length + 1  # +1 = system prompt
    if len(history) <= max_msgs:
        return history
    return [history[0]] + history[-(max_msgs - 1):]
