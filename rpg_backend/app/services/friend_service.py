"""
FriendService — друзья: запросы, принятие, отклонение, список.
"""

import sqlite3

from ..db import get_db


async def _tx(db) -> None:
    """Начать немедленную транзакцию."""
    await db.execute("BEGIN IMMEDIATE")


async def _rollback_quietly(db) -> None:
    """Откатить транзакцию, глуша вторичную ошибку отката."""
    try:
        await db.rollback()
    except Exception:
        pass


async def _run_tx(action) -> dict:
    """Общий каркас атомарных операций: BEGIN IMMEDIATE → action(db) → commit.

    ValueError от action пробрасывается как есть (контракт API-слоя),
    sqlite3.IntegrityError → «Запрос уже отправлен», прочее — rollback + raise.
    """
    db = await get_db()
    try:
        await _tx(db)
        try:
            result = await action(db)
            await db.commit()
            return result
        except sqlite3.IntegrityError:
            await _rollback_quietly(db)
            raise ValueError("Запрос уже отправлен")
        except Exception:
            await _rollback_quietly(db)
            raise
    finally:
        await db.close()


async def get_friends(user_id: str) -> dict:
    """Вернуть {'friends': [...], 'pending': [...], 'sent': [...]} — плоские списки."""
    db = await get_db()
    try:
        # Принятые друзья — двунаправленно
        rows = await db.execute(
            """SELECT fr.id, fr.from_user_id, fr.to_user_id, fr.status,
                      u.id AS user_id, u.username
               FROM friend_requests fr
               JOIN users u ON (
                   (u.id = fr.from_user_id AND fr.to_user_id = ?) OR
                   (u.id = fr.to_user_id AND fr.from_user_id = ?)
               )
               WHERE fr.status = 'accepted'
                 AND u.id != ?""",
            (user_id, user_id, user_id),
        )
        friends = []
        seen = set()
        for r in await rows.fetchall():
            if r["user_id"] not in seen:
                seen.add(r["user_id"])
                friends.append({
                    "user_id": r["user_id"],
                    "username": r["username"],
                    "status": "accepted",
                    "created_at": "",
                })

        # Входящие запросы (pending, где я — to_user_id)
        rows = await db.execute(
            """SELECT fr.id, fr.from_user_id, u.username, fr.created_at
               FROM friend_requests fr
               JOIN users u ON u.id = fr.from_user_id
               WHERE fr.to_user_id = ? AND fr.status = 'pending'""",
            (user_id,),
        )
        pending = []
        for r in await rows.fetchall():
            pending.append({
                "id": r["id"],
                "user_id": r["from_user_id"],
                "username": r["username"],
                "status": "pending",
                "created_at": r["created_at"],
            })

        # Исходящие запросы (pending, где я — from_user_id)
        rows = await db.execute(
            """SELECT fr.id, fr.to_user_id, u.username, fr.created_at
               FROM friend_requests fr
               JOIN users u ON u.id = fr.to_user_id
               WHERE fr.from_user_id = ? AND fr.status = 'pending'""",
            (user_id,),
        )
        sent = []
        for r in await rows.fetchall():
            sent.append({
                "id": r["id"],
                "user_id": r["to_user_id"],
                "username": r["username"],
                "status": "pending",
                "created_at": r["created_at"],
            })

        return {"friends": friends, "pending": pending, "sent": sent}
    finally:
        await db.close()


async def send_friend_request(from_user_id: str, to_username: str) -> dict:
    async def action(db):
        # Найти получателя
        cur = await db.execute(
            "SELECT id FROM users WHERE username = ?", (to_username,)
        )
        to_user = await cur.fetchone()
        if not to_user:
            raise ValueError("Пользователь не найден")
        to_id = to_user["id"]

        if to_id == from_user_id:
            raise ValueError("Нельзя добавить себя в друзья")

        # Проверить существующие отношения
        cur = await db.execute(
            """SELECT status FROM friend_requests
               WHERE (from_user_id = ? AND to_user_id = ?)
                  OR (from_user_id = ? AND to_user_id = ?)""",
            (from_user_id, to_id, to_id, from_user_id),
        )
        existing = await cur.fetchone()
        if existing:
            if existing["status"] == "accepted":
                raise ValueError("Уже друзья")
            if existing["status"] == "pending":
                raise ValueError("Запрос уже отправлен")

        await db.execute(
            "INSERT INTO friend_requests (from_user_id, to_user_id) VALUES (?, ?)",
            (from_user_id, to_id),
        )
        return {"ok": True}

    return await _run_tx(action)


async def accept_friend(user_id: str, request_id: int) -> dict:
    async def action(db):
        cur = await db.execute(
            "SELECT * FROM friend_requests WHERE id = ? AND to_user_id = ? AND status = 'pending'",
            (request_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Запрос не найден")

        await db.execute(
            "UPDATE friend_requests SET status = 'accepted' WHERE id = ?",
            (request_id,),
        )
        return {"ok": True}

    return await _run_tx(action)


async def reject_friend(user_id: str, request_id: int) -> dict:
    async def action(db):
        await db.execute(
            "DELETE FROM friend_requests WHERE id = ? AND to_user_id = ? AND status = 'pending'",
            (request_id, user_id),
        )
        return {"ok": True}

    return await _run_tx(action)


async def remove_friend(user_id: str, friend_user_id: str) -> dict:
    async def action(db):
        await db.execute(
            """DELETE FROM friend_requests
              WHERE status = 'accepted'
                AND (
                    (from_user_id = ? AND to_user_id = ?) OR
                    (from_user_id = ? AND to_user_id = ?)
                )""",
            (user_id, friend_user_id, friend_user_id, user_id),
        )
        return {"ok": True}

    return await _run_tx(action)


async def search_users(current_user_id: str, query: str) -> dict:
    """Поиск пользователей по username (без себя и без уже-друзей)."""
    db = await get_db()
    try:
        # Экранируем LIKE-спецсимволы, чтобы query не превращался в маску
        esc = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = await db.execute(
            """SELECT u.id, u.username
               FROM users u
               WHERE u.username LIKE ? ESCAPE '\\' AND u.id != ?
                 AND u.id NOT IN (
                   SELECT fr.to_user_id FROM friend_requests fr
                   WHERE fr.from_user_id = ? AND fr.status = 'accepted'
                   UNION
                   SELECT fr.from_user_id FROM friend_requests fr
                   WHERE fr.to_user_id = ? AND fr.status = 'accepted'
                   UNION
                   SELECT fr.to_user_id FROM friend_requests fr
                   WHERE fr.from_user_id = ? AND fr.status = 'pending'
                   UNION
                   SELECT fr.from_user_id FROM friend_requests fr
                   WHERE fr.to_user_id = ? AND fr.status = 'pending'
                 )
               ORDER BY u.username
               LIMIT 20""",
            (f"%{esc}%", current_user_id, current_user_id, current_user_id, current_user_id, current_user_id),
        )
        users = []
        for r in await rows.fetchall():
            users.append({
                "user_id": r["id"],
                "username": r["username"],
            })
        return {"users": users}
    finally:
        await db.close()


async def invite_friend_to_session(user_id: str, friend_user_id: str, session_id: str) -> dict:
    """Создать приглашение друга в сессию. Возвращает invite_code."""
    db = await get_db()
    try:
        # Проверить что они друзья
        cur = await db.execute(
            """SELECT 1 FROM friend_requests
               WHERE status = 'accepted'
                 AND ((from_user_id = ? AND to_user_id = ?)
                   OR (from_user_id = ? AND to_user_id = ?))""",
            (user_id, friend_user_id, friend_user_id, user_id),
        )
        if not await cur.fetchone():
            raise ValueError("Пользователь не в друзьях")

        # Проверить что сессия существует и юзер — владелец
        cur = await db.execute(
            "SELECT invite_code FROM game_sessions WHERE id = ? AND owner_id = ?",
            (session_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Сессия не найдена или вы не владелец")

        # Создать запись-приглашение (pending invite)
        invite_code = row["invite_code"]
        return {
            "ok": True,
            "invite_code": invite_code,
            "session_id": session_id,
            "friend_user_id": friend_user_id,
        }
    finally:
        await db.close()
