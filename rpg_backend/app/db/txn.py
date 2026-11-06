"""Общие async-хелперы для транзакций SQLite (aiosqlite).

Пакет-wide общий код: используется платежами (идемпотентность), сервисом
памяти (TOCTOU-защита), сервисом сессий (turn-order insertion / session purge),
групповым чатом (двойной LLM guard). Держим только паттерн BEGIN IMMEDIATE /
COMMIT / ROLLBACK, который иначе повторяется в каждом сервисе.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite


@asynccontextmanager
async def immediate_txn(db: aiosqlite.Connection) -> AsyncIterator[aiosqlite.Connection]:
    """Открыть транзакцию BEGIN IMMEDIATE с COMMIT / ROLLBACK по исключению.

    Общий шаблон для критических секций записи: без него каждый сервис повторяет
    `await db.execute("BEGIN IMMEDIATE") / commit / rollback` вручную (клоны в
    payments, memory_service, session_service). ROLLBACK идемпотентен: на
    соединении без активной транзакции это no-op, поэтому удвоенный rollback
    (внутренний + внешний обработчик) безопасен.
    """
    await db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        await db.rollback()
        raise
    else:
        await db.commit()


async def run_txn(db: aiosqlite.Connection, *statements: tuple[str, tuple]) -> list[aiosqlite.Cursor]:
    """Выполнить список (sql, params) в одной immediate-транзакции.

    Удобен для «удалить связанное + удалить кортеж» / upsert-цепочек:
    session purge, payments inserts. Возвращает курсоры в порядке выполнения.
    """
    cursors: list[aiosqlite.Cursor] = []
    async with immediate_txn(db):
        for sql, params in statements:
            cursors.append(await db.execute(sql, params))
    return cursors
