"""Пакет БД: подключение + миграции.

Реэкспорт get_db/init_db — импорты `from app.db import get_db` работают.
"""

from app.db.connection import DB_PATH, get_db
from app.db.migrations import init_db

__all__ = ["DB_PATH", "get_db", "init_db"]
