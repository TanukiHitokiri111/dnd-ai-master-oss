"""Сервисный слой системы очков умений классов.

Механика (требование владельца):
- У каждого умения 5 рангов. 1 очко умения = +1 ранг, максимум ранга = 5.
- Умение с рангом 0 = не изучено. Открыть новое умение = 1 очко (сразу ранг 1).
- ПРЕДПОСЫЛКИ: умение нельзя открыть, пока не открыты ВСЕ умения из его
  "prereq" (у каждого ранг >= 1). Одного из двух НЕДОСТАТОЧНО — нужны оба.
- Умение доступно для изучения, если: unlock_level <= уровень класса персонажа
  И все prereq открыты.

Модуль несовместимо-устойчив: отсутствие таблиц character_abilities, колонки
characters.ability_points, файла данных или ключа класса не является ошибкой.
"""

import json
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ABILITIES_PATH = os.environ.get("ABILITIES_PATH", "/app/data/class_abilities.json")

MAX_RANK = 5

_CHARACTER_ABILITIES_SQL = """
CREATE TABLE IF NOT EXISTS character_abilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    ability_key TEXT NOT NULL,
    class_key TEXT NOT NULL DEFAULT '',
    rank INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(character_id, ability_key)
)
"""


# ── Ленивая инициализация схемы ─────────────────────────────────────────────

async def ensure_ability_schema(db) -> None:
    """Идемпотентная инициализация схемы системы умений.

    Создаёт при отсутствии: колонку characters.ability_points и таблицу
    character_abilities. Можно вызывать сколько угодно раз — повторные
    вызовы ничего не меняют. Все исключения глотаются: сбой схемы
    (read-only БД и т.п.) не должен ломать вызывающий код.
    """
    # 1) колонка ability_points в characters
    try:
        cur = await db.execute("PRAGMA table_info(characters)")
        cols = {str(row[1]) for row in await cur.fetchall()}
        if "ability_points" not in cols:
            await db.execute(
                "ALTER TABLE characters ADD COLUMN ability_points INTEGER NOT NULL DEFAULT 0"
            )
    except Exception:
        pass
    # 2) таблица character_abilities (character_id — TEXT: id персонажа это hex-строка)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='character_abilities'"
        )
        if not await cur.fetchone():
            await db.execute(_CHARACTER_ABILITIES_SQL)
    except Exception:
        pass
    # 3) фиксация изменений
    try:
        await db.commit()
    except Exception:
        pass


# ── Загрузка данных умений ──────────────────────────────────────────────────

def load_class_abilities(class_key: str) -> List[dict]:
    """Список умений класса. Безопасно: нет файла / битый JSON / нет ключа
    / любое исключение → [] (не падать)."""
    try:
        with open(ABILITIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    abilities = data.get(class_key)
    if not isinstance(abilities, list):
        return []
    return [a for a in abilities if isinstance(a, dict)]


# ── Чтение состояния персонажа ──────────────────────────────────────────────

async def get_class_level(db, char_id: str, class_key: str) -> int:
    """Уровень персонажа В ЭТОМ КЛАССЕ.

    Сначала таблица character_classes (character_id, class_name, level).
    Если строки нет — фолбэк на characters.level основного класса
    (class_name == class_key). Иначе 0.
    """
    class_key = class_key or ""
    # 1) многклассовая таблица
    try:
        cur = await db.execute(
            "SELECT level FROM character_classes WHERE character_id = ? AND class_name = ? LIMIT 1",
            (char_id, class_key),
        )
        row = await cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass  # таблицы может не быть — идём в фолбэк
    # 2) фолбэк: основной класс в characters
    try:
        cur = await db.execute(
            "SELECT level FROM characters WHERE id = ? AND class_name = ? LIMIT 1",
            (char_id, class_key),
        )
        row = await cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    return 0


async def get_learned(db, char_id: str) -> Dict[str, int]:
    """Изученные умения: {ability_key: rank}. Таблица character_abilities
    может ещё не существовать → {}. Существование проверяем через sqlite_master."""
    await ensure_ability_schema(db)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='character_abilities'"
        )
        if not await cur.fetchone():
            return {}
        cur = await db.execute(
            "SELECT ability_key, rank FROM character_abilities WHERE character_id = ?",
            (char_id,),
        )
        rows = await cur.fetchall()
    except Exception:
        return {}
    return {str(k): int(r) for k, r in rows if k is not None}


async def get_ability_points(db, char_id: str) -> int:
    """Неизрасходованные очки из characters.ability_points.
    Колонка может отсутствовать → 0 (проверка через pragma_table_info)."""
    await ensure_ability_schema(db)
    try:
        cur = await db.execute("PRAGMA table_info(characters)")
        cols = await cur.fetchall()
        if not any(str(row[1]) == "ability_points" for row in cols):
            return 0
        cur = await db.execute(
            "SELECT COALESCE(ability_points, 0) FROM characters WHERE id = ? LIMIT 1",
            (char_id,),
        )
        row = await cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    return 0


# ── Вычисление видимых умений ───────────────────────────────────────────────

def _full_entry(ability: dict, rank: int, points_needed: Optional[int] = None) -> dict:
    """Полное описание умения для ответа клиенту."""
    entry = {
        "key": ability.get("key", ""),
        "name": ability.get("name", ""),
        "desc": ability.get("desc", ""),
        "unlock_level": ability.get("unlock_level", 1),
        "type": ability.get("type", "passive"),
        "stat": ability.get("stat", ""),
        "ranks": ability.get("ranks", []),
        "rank": rank,
        "max_rank": MAX_RANK,
        "prereq": list(ability.get("prereq") or []),
    }
    if points_needed is not None:
        entry["points_needed"] = points_needed
    return entry


def compute_visible(class_key: str, class_level: int, learned: Dict[str, int]) -> dict:
    """Что игрок ВИДИТ (показывать не всё): {"learned", "available", "next"}.

    - learned:   умения с rank >= 1 (с текущим рангом).
    - available: unlock_level <= class_level, все prereq открыты, rank == 0
                 (можно изучать прямо сейчас).
    - next:      тизер — rank == 0, unlock_level <= class_level, prereq ещё не
                 все открыты, но все недостающие prereq лежат среди available.
                 Помечено "locked": true и "missing_prereq": [...].
    Всё остальное скрыто.
    """
    learned = learned or {}
    abilities = load_class_abilities(class_key)

    learned_out: List[dict] = []
    available_keys: set = set()
    available_out: List[dict] = []

    # Промежуточное состояние для расчёта тизеров.
    pending: List[tuple] = []  # (ability, missing_prereq)

    for ability in abilities:
        key = ability.get("key", "")
        rank = int(learned.get(key, 0))
        if rank >= 1:
            learned_out.append(_full_entry(ability, rank))
            continue
        # rank == 0: учим уровень и предпосылки
        prereq = list(ability.get("prereq") or [])
        missing = [p for p in prereq if int(learned.get(p, 0)) < 1]
        if int(ability.get("unlock_level", 1)) <= class_level:
            if not missing:
                available_keys.add(key)
                available_out.append(_full_entry(ability, 0, points_needed=1))
            else:
                pending.append((ability, missing))

    next_out: List[dict] = []
    for ability, missing in pending:
        if all(m in available_keys for m in missing):
            entry = _full_entry(ability, 0, points_needed=1)
            entry["locked"] = True
            entry["missing_prereq"] = missing
            next_out.append(entry)

    return {"learned": learned_out, "available": available_out, "next": next_out}


# ── Валидация распределения очков ───────────────────────────────────────────

def validate_allocation(
    class_key: str,
    class_level: int,
    learned: Dict[str, int],
    points: int,
    allocations: Sequence[dict],
) -> Tuple[bool, str]:
    """Проверка распределения очков.

    allocations: [{"ability_key": str, "ranks": int}] — сколько РАНГОВ добавить
    (прибавка, не итоговый ранг). Возвращает (True, "") или (False, сообщение).
    """
    learned = learned or {}
    abilities = load_class_abilities(class_key)
    by_key = {a.get("key"): a for a in abilities}

    # 0) ranks > 0
    for alloc in allocations or []:
        try:
            ranks = int(alloc.get("ranks", 0))
        except (TypeError, ValueError):
            return False, "Некорректное количество рангов."
        if ranks <= 0:
            return False, "Количество рангов должно быть больше нуля."

    # 1) перерасход очков запрещён (потратить не все — можно)
    total = sum(int(a.get("ranks", 0)) for a in allocations or [])
    if total > int(points):
        return False, (
            f"Недостаточно очков умений: требуется {total}, доступно {int(points)}."
        )

    # Итоговые ранги с учётом уже запланированных в этих же allocations —
    # порядок применения не должен ломать цепочку предпосылок.
    planned: Dict[str, int] = {}
    for alloc in allocations or []:
        key = alloc.get("ability_key")
        planned[key] = planned.get(key, 0) + int(alloc.get("ranks", 0))

    def rank_after(key: str) -> int:
        return int(learned.get(key, 0)) + planned.get(key, 0)

    for key in planned:
        ability = by_key.get(key)
        # 2) умение существует в классе
        if ability is None:
            return False, f"Умение «{key}» не найдено в классе {class_key}."
        # 3) уровень класса
        if int(ability.get("unlock_level", 1)) > int(class_level):
            return False, (
                f"Умение «{ability.get('name', key)}» открывается на "
                f"{int(ability.get('unlock_level', 1))} уровне класса "
                f"(сейчас {int(class_level)})."
            )
        # 4) все prereq открыты (с учётом планируемых)
        for p in ability.get("prereq") or []:
            if rank_after(p) < 1:
                return False, (
                    f"Умение «{ability.get('name', key)}» требует изученных "
                    f"предпосылок: «{p}»."
                )
        # 5) итоговый ранг <= 5
        final_rank = rank_after(key)
        if final_rank > MAX_RANK:
            return False, (
                f"Максимальный ранг умения — {MAX_RANK} "
                f"(«{ability.get('name', key)}»: итог {final_rank})."
            )

    return True, ""


# ── Применение распределения ────────────────────────────────────────────────

async def apply_allocation(db, char_id: str, class_key: str, allocations: Sequence[dict]) -> None:
    """Записать новые ранги в character_abilities и списать очки.

    Вызывать ПОСЛЕ validate_allocation(). Если таблицы нет — создаёт её сам
    (CREATE TABLE IF NOT EXISTS, только внутри этого модуля).
    """
    await ensure_ability_schema(db)
    allocations = allocations or []
    learned = await get_learned(db, char_id)
    abilities = load_class_abilities(class_key)
    by_key = {a.get("key"): a for a in abilities}

    # Таблица character_abilities (её может ещё не быть — создаём здесь).
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='character_abilities'"
    )
    if not await cur.fetchone():
        await db.execute(_CHARACTER_ABILITIES_SQL)

    spent = 0
    for alloc in allocations:
        key = alloc.get("ability_key")
        try:
            add = int(alloc.get("ranks", 0))
        except (TypeError, ValueError):
            continue
        if add <= 0 or key not in by_key:
            continue
        new_rank = int(learned.get(key, 0)) + add
        if new_rank > MAX_RANK:
            new_rank = MAX_RANK
        await db.execute(
            """
            INSERT INTO character_abilities
                (character_id, ability_key, class_key, rank, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(character_id, ability_key)
            DO UPDATE SET rank = excluded.rank,
                          class_key = excluded.class_key,
                          updated_at = datetime('now')
            """,
            (str(char_id), key, class_key, new_rank),
        )
        spent += add

    # Списать потраченные очки + updated_at у персонажа.
    # Колонки ability_points/updated_at могут отсутствовать (проверяем через
    # pragma_table_info, как и в get_ability_points) — тогда пропускаем шаг.
    cur = await db.execute("PRAGMA table_info(characters)")
    char_cols = {str(row[1]) for row in await cur.fetchall()}
    if spent > 0 and "ability_points" in char_cols:
        cur = await db.execute(
            "SELECT ability_points FROM characters WHERE id = ?", (char_id,)
        )
        row = await cur.fetchone()
        current = int(row[0]) if row and row[0] is not None else 0
        await db.execute(
            "UPDATE characters SET ability_points = ?, updated_at = datetime('now') WHERE id = ?",
            (max(0, current - spent), char_id),
        )
    elif "updated_at" in char_cols:
        await db.execute(
            "UPDATE characters SET updated_at = datetime('now') WHERE id = ?", (char_id,)
        )

    await db.commit()


# ── Синхронный адаптер (для скриптов/CLI без asyncio-драйвера) ──────────────

class _SyncCursor:
    """Тонкая обёртка над sqlite3.Cursor с async-совместимым интерфейсом."""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchall(self):
        return self._cursor.fetchall()


class SyncConnection:
    """Обёртка над sqlite3.Connection, совместимая с async-интерфейсом сервиса.

    Позволяет вызывать get_learned/apply_allocation и т.д. из обычных скриптов
    с синхронным sqlite3 (get_learned(db, ...) и т.п. работают без изменений).
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    async def execute(self, sql: str, params: Iterable = ()):  # noqa: D102
        return _SyncCursor(self._conn.execute(sql, tuple(params)))

    async def commit(self) -> None:
        self._conn.commit()
