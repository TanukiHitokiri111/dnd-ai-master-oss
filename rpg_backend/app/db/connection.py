"""
Модуль базы данных: aiosqlite + schema v2.
Полноценный инвентарь, предыстория, черты, владения.
"""

import aiosqlite
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # проект /app/
DB_PATH = BASE_DIR / "data" / "rpg.db"


async def get_db() -> aiosqlite.Connection:
    """Получить подключение к БД."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")
    return db
