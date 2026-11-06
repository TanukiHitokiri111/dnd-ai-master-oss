"""
REST API для игровых сессий (мультиплеер).
v3.0.0.12-patched: фиксы безопасности — членство, rate limit, валидация, утечки.
"""

import time
import secrets
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional

from ...services import session_service
from app.deps import get_current_user
from app.logger import logger

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _is_session_member(session: dict | None, user_id: str) -> bool:
    """True если сессия существует и user_id входит в её members.

    Общий предикат для sessions.py (_require_member → HTTP 403/404) и ws.py
    (connect/chat-guard → WebSocket close): проверка одинаковая, различается
    только способ сообщения об ошибке.
    """
    if not session:
        return False
    member_ids = [m["user_id"] for m in session.get("members", [])]
    return user_id in member_ids



# Простой in-memory rate limiter для join (на перезапуск сбрасывается — ок для MVP)
_JOIN_ATTEMPTS: dict[str, list[float]] = {}  # key -> [timestamps]
_JOIN_MAX_ATTEMPTS = 5
_JOIN_WINDOW = 60  # секунд
_JOIN_LAST_CLEANUP = time.time()


def _check_join_rate(key: str) -> bool:
    """True если можно пробовать, False если превышен лимит."""
    global _JOIN_ATTEMPTS, _JOIN_LAST_CLEANUP
    now = time.time()
    attempts = [t for t in _JOIN_ATTEMPTS.get(key, []) if now - t < _JOIN_WINDOW]
    if len(attempts) >= _JOIN_MAX_ATTEMPTS:
        _JOIN_ATTEMPTS[key] = attempts
        return False
    attempts.append(now)
    _JOIN_ATTEMPTS[key] = attempts

    # Периодическая очистка мёртвых ключей
    if now - _JOIN_LAST_CLEANUP > 300:
        _JOIN_ATTEMPTS = {k: v for k, v in _JOIN_ATTEMPTS.items() if v}
        _JOIN_LAST_CLEANUP = now
    return True


class CreateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class JoinSessionRequest(BaseModel):
    invite_code: str = Field(..., min_length=8, max_length=10, pattern=r"^[A-Z0-9]+$")


class SetReadyRequest(BaseModel):
    character_id: str


# ─── Вспомогательная зависимость: проверить членство ───

async def _require_member(session_id: str, user_id: str) -> dict:
    """Проверить что пользователь — участник сессии. Возвращает сессию или 403/404."""
    s = await session_service.get_session(session_id)
    if not s:
        raise HTTPException(404, "Сессия не найдена")
    if not _is_session_member(s, user_id):
        raise HTTPException(403, "Вы не участник этой сессии")
    return s


# ─── CRUD ───

@router.post("")
async def create_session(req: CreateSessionRequest, user_id: str = Depends(get_current_user)):
    try:
        return await session_service.create_session(user_id, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_sessions(user_id: str = Depends(get_current_user)):
    sessions = await session_service.list_user_sessions(user_id)
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session(session_id: str, user_id: str = Depends(get_current_user)):
    s = await _require_member(session_id, user_id)
    return s


@router.post("/join")
async def join_session(req: JoinSessionRequest, user_id: str = Depends(get_current_user),
                        request: Request = None):
    # Rate limit: по user_id + IP
    client_ip = request.client.host if request else "unknown"
    for key in (user_id, client_ip):
        if not _check_join_rate(key):
            logger.warning("Join rate limit hit: user=%s ip=%s", user_id[:8], client_ip)
            raise HTTPException(429, "Слишком много попыток. Подождите минуту.")
    try:
        return await session_service.join_session(user_id, req.invite_code.strip().upper())
    except ValueError as e:
        raise HTTPException(404, str(e))
    except aiosqlite.IntegrityError:
        raise HTTPException(409, "Вы уже присоединились к этой сессии")


@router.delete("/{session_id}/leave")
async def leave_session(session_id: str, user_id: str = Depends(get_current_user)):
    ok = await session_service.leave_session(user_id, session_id)
    return {"ok": ok}


@router.delete("/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(get_current_user)):
    ok = await session_service.delete_session(user_id, session_id)
    if not ok:
        raise HTTPException(403, "Не владелец или сессия не найдена")
    return {"ok": True}


# ─── Lobby actions ───

@router.post("/{session_id}/ready")
async def set_ready(session_id: str, req: SetReadyRequest,
                    user_id: str = Depends(get_current_user)):
    await _require_member(session_id, user_id)
    try:
        return await session_service.set_ready(user_id, session_id, req.character_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{session_id}/start")
async def start_session(session_id: str, user_id: str = Depends(get_current_user)):
    s = await _require_member(session_id, user_id)
    if s.get("owner_id") != user_id:
        raise HTTPException(403, "Только создатель сессии может начать игру")
    try:
        return await session_service.start_session(session_id, user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─── Game actions ───

@router.post("/{session_id}/initiative")
async def roll_initiative(session_id: str, user_id: str = Depends(get_current_user)):
    await _require_member(session_id, user_id)
    s = await session_service.get_session(session_id)
    if s.get("owner_id") != user_id:
        raise HTTPException(403, "Только создатель сессии может управлять боем")
    try:
        return await session_service.roll_initiative(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{session_id}/next-turn")
async def next_turn(session_id: str, user_id: str = Depends(get_current_user)):
    await _require_member(session_id, user_id)
    s = await session_service.get_session(session_id)
    if s.get("owner_id") != user_id:
        raise HTTPException(403, "Только создатель сессии может управлять боем")
    try:
        return await session_service.next_turn(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─── Chat history ───

@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    user_id: str = Depends(get_current_user),
):
    await _require_member(session_id, user_id)
    messages = await session_service.get_session_messages(session_id, limit)
    return {"messages": messages}
