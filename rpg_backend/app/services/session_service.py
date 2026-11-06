"""
SessionService — управление игровыми сессиями (мультиплеер).
Создание, присоединение, готовность, старт, инициатива, ходы.
"""

import uuid
import secrets
import json
from typing import Optional

from ..db import get_db

# Буквы без путаницы: убраны I, O, 0, 1
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _gen_invite_code() -> str:
    """8-символьный криптостойкий код."""
    return ''.join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))


def _gen_id() -> str:
    return str(uuid.uuid4())


async def create_session(user_id: str, name: str) -> dict:
    """Создать сессию. Создатель становится owner + member."""
    db = await get_db()
    try:
        sid = _gen_id()
        invite = _gen_invite_code()

        await db.execute(
            "INSERT INTO game_sessions (id, name, owner_id, invite_code) VALUES (?, ?, ?, ?)",
            (sid, name, user_id, invite),
        )
        await db.execute(
            "INSERT INTO session_members (session_id, user_id, role, turn_order) VALUES (?, ?, 'owner', 0)",
            (sid, user_id),
        )
        await db.commit()
        return await _get_session_dict(db, sid)
    finally:
        await db.close()


async def get_session(session_id: str) -> Optional[dict]:
    db = await get_db()
    try:
        return await _get_session_dict(db, session_id)
    finally:
        await db.close()


async def list_user_sessions(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute(
            """SELECT s.id FROM game_sessions s
               JOIN session_members sm ON sm.session_id = s.id
               WHERE sm.user_id = ?
               ORDER BY s.created_at DESC""",
            (user_id,),
        )
        ids = [r["id"] for r in await rows.fetchall()]
        return [await _get_session_dict(db, sid) for sid in ids]
    finally:
        await db.close()


async def join_session(user_id: str, invite_code: str) -> dict:
    db = await get_db()
    try:
        # Найти сессию по коду
        cur = await db.execute(
            "SELECT id FROM game_sessions WHERE invite_code = ?", (invite_code,)
        )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Сессия не найдена")

        sid = row["id"]

        # Уже участник?
        cur = await db.execute(
            "SELECT 1 FROM session_members WHERE session_id = ? AND user_id = ?",
            (sid, user_id),
        )
        if await cur.fetchone():
            return await _get_session_dict(db, sid)

        # Максимальный turn_order
        cur = await db.execute(
            "SELECT MAX(turn_order) as mo FROM session_members WHERE session_id = ?",
            (sid,),
        )
        max_order = (await cur.fetchone())["mo"] or 0

        await db.execute(
            "INSERT INTO session_members (session_id, user_id, turn_order) VALUES (?, ?, ?)",
            (sid, user_id, max_order + 1),
        )
        await db.commit()
        return await _get_session_dict(db, sid)
    finally:
        await db.close()


async def leave_session(user_id: str, session_id: str) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM session_members WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        # Если никого не осталось — удаляем сессию
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM session_members WHERE session_id = ?",
            (session_id,),
        )
        if (await cur.fetchone())["cnt"] == 0:
            await db.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
        await db.commit()
        return True
    finally:
        await db.close()


async def delete_session(owner_id: str, session_id: str) -> bool:
    """Удалить сессию полностью. Только владелец может удалить."""
    db = await get_db()
    try:
        # Проверить владельца
        cur = await db.execute(
            "SELECT owner_id FROM game_sessions WHERE id = ?", (session_id,)
        )
        row = await cur.fetchone()
        if not row:
            return False
        if row["owner_id"] != owner_id:
            return False

        # Удалить всё связанное
        await db.execute("DELETE FROM group_chat_history WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM session_members WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
        await db.commit()
        return True
    finally:
        await db.close()


async def set_ready(user_id: str, session_id: str, character_id: str) -> dict:
    db = await get_db()
    try:
        await db.execute(
            """UPDATE session_members
               SET is_ready = 1, character_id = ?
               WHERE session_id = ? AND user_id = ?""",
            (character_id, session_id, user_id),
        )
        await db.commit()
        return await _get_session_dict(db, session_id)
    finally:
        await db.close()


async def start_session(session_id: str, owner_id: str) -> dict:
    db = await get_db()
    try:
        # Проверить что все ready
        cur = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN is_ready=1 THEN 1 ELSE 0 END) as ready
               FROM session_members WHERE session_id = ?""",
            (session_id,),
        )
        stats = await cur.fetchone()
        if stats["total"] < 2:
            raise ValueError("Нужно минимум 2 игрока")
        if stats["ready"] != stats["total"]:
            raise ValueError("Не все игроки готовы")

        await db.execute(
            "UPDATE game_sessions SET state = 'playing' WHERE id = ? AND owner_id = ?",
            (session_id, owner_id),
        )
        await db.commit()
        return await _get_session_dict(db, session_id)
    finally:
        await db.close()


async def roll_initiative(session_id: str) -> dict:
    """Бросить инициативу для всех участников и отсортировать."""
    import random as rnd
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id FROM session_members WHERE session_id = ?", (session_id,)
        )
        members = await cur.fetchall()

        for i, m in enumerate(members):
            init = rnd.randint(1, 20)
            await db.execute(
                "UPDATE session_members SET initiative = ?, turn_order = ? WHERE id = ?",
                (init, i, m["id"]),
            )

        # Сортировка по инициативе (descending) — переназначить turn_order
        cur = await db.execute(
            "SELECT id FROM session_members WHERE session_id = ? ORDER BY initiative DESC",
            (session_id,),
        )
        sorted_members = await cur.fetchall()
        for i, m in enumerate(sorted_members):
            await db.execute(
                "UPDATE session_members SET turn_order = ? WHERE id = ?",
                (i, m["id"]),
            )

        # Установить current_turn_user_id первого
        first_member = await db.execute(
            """SELECT sm.user_id FROM session_members sm
               WHERE sm.session_id = ? ORDER BY sm.turn_order ASC LIMIT 1""",
            (session_id,),
        )
        first = await first_member.fetchone()
        if first:
            await db.execute(
                "UPDATE game_sessions SET current_turn_user_id = ?, turn_index = 0 WHERE id = ?",
                (first["user_id"], session_id),
            )

        await db.commit()
        return await _get_session_dict(db, session_id)
    finally:
        await db.close()


async def next_turn(session_id: str) -> dict:
    """Передать ход следующему игроку."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT turn_index FROM game_sessions WHERE id = ?", (session_id,)
        )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Сессия не найдена")
        current_index = row["turn_index"]

        # Посчитать число игроков
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM session_members WHERE session_id = ?",
            (session_id,),
        )
        total = (await cur.fetchone())["cnt"]
        next_index = (current_index + 1) % total

        # Найти user_id с этим turn_order
        cur = await db.execute(
            "SELECT user_id FROM session_members WHERE session_id = ? AND turn_order = ?",
            (session_id, next_index),
        )
        member = await cur.fetchone()
        if member:
            await db.execute(
                "UPDATE game_sessions SET turn_index = ?, current_turn_user_id = ? WHERE id = ?",
                (next_index, member["user_id"], session_id),
            )

        await db.commit()
        return await _get_session_dict(db, session_id)
    finally:
        await db.close()


async def get_session_messages(session_id: str, limit: int = 100) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM group_chat_history
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (session_id, limit),
        )
        rows = await cur.fetchall()
        return [_chat_row_to_dict(r) for r in reversed(rows)]
    finally:
        await db.close()


async def save_session_message(
    session_id: str, user_id: str, role: str, content: str,
    character_id: Optional[str] = None, dice_roll: Optional[dict] = None,
) -> dict:
    db = await get_db()
    try:
        cur = await db.execute(
            """INSERT INTO group_chat_history
               (session_id, user_id, character_id, role, content, dice_roll)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session_id, user_id, character_id, role, content,
                json.dumps(dice_roll) if dice_roll else None,
            ),
        )
        await db.commit()
        msg_id = cur.lastrowid
        cur = await db.execute(
            "SELECT * FROM group_chat_history WHERE id = ?", (msg_id,)
        )
        return _chat_row_to_dict(await cur.fetchone())
    finally:
        await db.close()


# ─── Helpers ───

async def _get_session_dict(db, session_id: str) -> Optional[dict]:
    cur = await db.execute("SELECT * FROM game_sessions WHERE id = ?", (session_id,))
    row = await cur.fetchone()
    if not row:
        return None

    members_cur = await db.execute(
        """SELECT sm.*, u.username,
                  c.name AS character_name,
                  c.stats AS character_stats_json
           FROM session_members sm
           JOIN users u ON u.id = sm.user_id
           LEFT JOIN characters c ON c.id = sm.character_id
           WHERE sm.session_id = ?
           ORDER BY sm.turn_order ASC""",
        (session_id,),
    )
    members = []
    for m in await members_cur.fetchall():
        char_stats = None
        if m["character_stats_json"]:
            try:
                char_stats = json.loads(m["character_stats_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        members.append({
            "id": m["id"],
            "user_id": m["user_id"],
            "character_id": m["character_id"],
            "role": m["role"],
            "initiative": m["initiative"],
            "turn_order": m["turn_order"],
            "is_ready": bool(m["is_ready"]),
            "username": m["username"],
            "character_name": m["character_name"],
            "character_stats": char_stats,
        })

    return {
        "id": row["id"],
        "name": row["name"],
        "owner_id": row["owner_id"],
        "invite_code": row["invite_code"],
        "state": row["state"],
        "turn_index": row["turn_index"],
        "current_turn_user_id": row["current_turn_user_id"],
        "created_at": row["created_at"],
        "members": members,
    }


def _chat_row_to_dict(row) -> dict:
    dice = None
    if row["dice_roll"]:
        try:
            dice = json.loads(row["dice_roll"])
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "character_id": row["character_id"],
        "role": row["role"],
        "content": row["content"],
        "dice_roll": dice,
        "created_at": row["created_at"],
    }
