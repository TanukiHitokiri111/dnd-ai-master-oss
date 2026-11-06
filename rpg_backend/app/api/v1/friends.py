"""
REST API для друзей.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...services import friend_service
from app.deps import get_current_user

router = APIRouter(prefix="/friends", tags=["friends"])


class FriendRequest(BaseModel):
    username: str


@router.get("")
async def list_friends(user_id: str = Depends(get_current_user)):
    return await friend_service.get_friends(user_id)


@router.post("/request")
async def send_friend_request(req: FriendRequest, user_id: str = Depends(get_current_user)):
    try:
        return await friend_service.send_friend_request(user_id, req.username)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/accept/{request_id}")
async def accept_friend(request_id: int, user_id: str = Depends(get_current_user)):
    try:
        return await friend_service.accept_friend(user_id, request_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/reject/{request_id}")
async def reject_friend(request_id: int, user_id: str = Depends(get_current_user)):
    try:
        return await friend_service.reject_friend(user_id, request_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{friend_user_id}")
async def remove_friend(friend_user_id: str, user_id: str = Depends(get_current_user)):
    try:
        return await friend_service.remove_friend(user_id, friend_user_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/search")
async def search_users(q: str = Query("", max_length=100), user_id: str = Depends(get_current_user)):
    """Поиск пользователей по username."""
    if not q.strip():
        return {"users": []}
    return await friend_service.search_users(user_id, q)


class InviteFriendRequest(BaseModel):
    friend_user_id: str


@router.post("/invite_to_session/{session_id}")
async def invite_friend_to_session(
    session_id: str, req: InviteFriendRequest, user_id: str = Depends(get_current_user)
):
    """Пригласить друга в сессию — отправляет invite-код через систему."""
    try:
        return await friend_service.invite_friend_to_session(user_id, req.friend_user_id, session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
