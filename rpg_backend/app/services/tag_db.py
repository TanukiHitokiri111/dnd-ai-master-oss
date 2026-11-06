"""Общие async-хелперы работы с SQLite для tag_processor миксинов.

Повторяющийся шаблон «открыть соединение → выполнить SELECT/UPDATE → закрыть»
жил копиями в npc.py, appearance.py, companions.py и прогрессии. Все обращения
к этим таблицам теперь идут через функции здесь.

Все функции возвращают простые dict-строки (sqlite3.Row → dict(row)).
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.db import get_db
from app.logger import logger


async def fetch_rows(sql: str, params: tuple = ()) -> list[dict]:
    """Выполнить SELECT и вернуть список dict-строк (соединение закрывается)."""
    db = await get_db()
    try:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Выполнить SELECT первой строки и вернуть dict (или None)."""
    db = await get_db()
    try:
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def execute_write(sql: str, params: tuple = ()) -> None:
    """Выполнить одиночный UPDATE/INSERT/DELETE с commit и закрытием."""
    db = await get_db()
    try:
        await db.execute(sql, params)
        await db.commit()
    finally:
        await db.close()


# ── Таблица npc_appearance (реестр внешностей NPC по character_id) ──


NPC_APPEARANCE_SELECT = (
    "SELECT rowid AS _rowid, npc_name, appearance, appearance_url "
    "FROM npc_appearance WHERE character_id = ?"
)


async def get_npc_appearance_row(character_id: str, npc_name: str) -> dict | None:
    """Точное совпадение по имени NPC."""
    return await fetch_one(
        "SELECT rowid AS _rowid, appearance, appearance_url FROM npc_appearance "
        "WHERE character_id = ? AND npc_name = ?",
        (character_id, npc_name),
    )


async def get_npc_appearance_rows(character_id: str) -> list[dict]:
    """Все NPC-внешности персонажа (для LLM-сравнения «тот же NPC?»)."""
    return await fetch_rows(NPC_APPEARANCE_SELECT, (character_id,))


async def upsert_npc_appearance_url(
    character_id: str, npc_name: str, appearance: str, url: str | None
) -> None:
    """UPDATE по rowid невозможен (rowid не знаем) → upsert по (character_id, npc_name)."""
    if url:
        await execute_write(
            """
            INSERT INTO npc_appearance (character_id, npc_name, appearance, appearance_url, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(character_id, npc_name)
            DO UPDATE SET appearance = excluded.appearance, appearance_url = excluded.appearance_url,
                          updated_at = datetime('now')
            """,
            (character_id, npc_name, appearance, url),
        )
    else:
        await execute_write(
            """
            INSERT INTO npc_appearance (character_id, npc_name, appearance, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(character_id, npc_name)
            DO UPDATE SET appearance = excluded.appearance, updated_at = datetime('now')
            """,
            (character_id, npc_name, appearance),
        )


# ── Реестр состояний npcs (alive/location/attitude) ──


def parse_npc_state_parts(raw: str, default_location: str) -> dict:
    """Разобрать [NPC_STATE: имя|статус|локация|отношение] → dict полей."""
    parts = [p.strip() for p in raw.split("|")]
    name = parts[0] if len(parts) > 0 and parts[0] else ""
    status = parts[1].lower() if len(parts) > 1 and parts[1] else ""
    location = parts[2] if len(parts) > 2 and parts[2] else default_location
    attitude = parts[3] if len(parts) > 3 and parts[3] else ""
    return {"name": name, "status": status, "location": location, "attitude": attitude}


NPC_DEAD_STATUSES = frozenset({
    "мёртв", "мертв", "убит", "погиб", "мёртва", "мертва", "убита",
    "dead", "умер", "умерла", "труп",
})


async def upsert_npc_state(
    character_id: str, name: str, alive: int, location: str, attitude: str
) -> None:
    """Регистрация/обновление стейта NPC из [NPC_STATE: ...]."""
    await execute_write(
        """INSERT INTO npcs (character_id, npc_name, alive, location, attitude, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(character_id, npc_name) DO UPDATE SET
             alive = CASE WHEN excluded.alive = 0 THEN 0 ELSE npcs.alive END,
             location = CASE WHEN excluded.location != '' THEN excluded.location ELSE npcs.location END,
             attitude = CASE WHEN excluded.attitude != '' THEN excluded.attitude ELSE npcs.attitude END,
             updated_at = datetime('now')""",
        (character_id, name, alive, location, attitude),
    )


async def upsert_npc_authorregistered(
    character_id: str, name: str, desc: str, location: str
) -> None:
    """Авторегистрация NPC из [NPC: имя|описание]: UPDATE если есть, иначе INSERT alive=1."""
    row = await fetch_one(
        "SELECT id FROM npcs WHERE character_id = ? AND npc_name = ?",
        (character_id, name),
    )
    if row:
        await execute_write(
            """UPDATE npcs SET description = CASE WHEN ? != '' THEN ? ELSE description END,
               location = CASE WHEN ? != '' THEN ? ELSE location END,
               updated_at = datetime('now')
               WHERE character_id = ? AND npc_name = ?""",
            (desc, desc, location, location, character_id, name),
        )
    else:
        await execute_write(
            """INSERT INTO npcs (character_id, npc_name, description, location, alive, updated_at)
               VALUES (?, ?, ?, ?, 1, datetime('now'))""",
            (character_id, name, desc, location),
        )
