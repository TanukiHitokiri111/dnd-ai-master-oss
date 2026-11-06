"""Зависимости FastAPI: авторизация, БД."""

from fastapi import Header, HTTPException, status

from app.auth import decode_token
from app.config import settings
from app.db import get_db

_BLOCKED_MESSAGE = (
    "Доступ заблокирован. "
    "Оплатите доступ через ЮKassa или активируйте код доступа."
)

_EXPIRED_MESSAGE = (
    "Срок действия доступа истёк. "
    "Продлите доступ через ЮKassa или активируйте новый код."
)


def _parse_bearer_user_id(authorization: str) -> str:
    """Извлечь user_id из заголовка Authorization: Bearer <JWT>.

    Общий парсер для get_current_user и get_current_user_allow_blocked:
    бросает 401 при отсутствии/невалидности токена.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется заголовок Authorization: Bearer <token>",
        )
    try:
        payload = decode_token(authorization[7:])
        return payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен",
        )


async def get_current_user(authorization: str = Header(...)) -> str:
    """Извлечь user_id из JWT токена + проверка is_active + subscription_expires."""
    user_id = _parse_bearer_user_id(authorization)

    # Открытый режим: подписка и активация не проверяются
    if not settings.require_access:
        return user_id

    # Проверка is_active И subscription_expires (один запрос — без TOCTOU)
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT is_active, subscription_expires, "
            "datetime(subscription_expires) < datetime('now') AS expired "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        user = await row.fetchone()
        if not user or not int(user["is_active"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BLOCKED_MESSAGE,
            )

        # Проверяем что код доступа не истёк (если есть дата истечения)
        if user["subscription_expires"] and user["expired"]:
            # Деактивируем пользователя (атомарно: только если expires не изменился)
            cur = await db.execute(
                "UPDATE users SET is_active = 0 WHERE id = ? AND is_active = 1 "
                "AND datetime(subscription_expires) = datetime(?) "
                "AND datetime(subscription_expires) < datetime('now')",
                (user_id, user["subscription_expires"]),
            )
            if cur.rowcount > 0:
                await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_EXPIRED_MESSAGE,
            )
    finally:
        await db.close()

    return user_id


async def get_current_user_allow_blocked(authorization: str = Header(...)) -> str:
    """Извлечь user_id из JWT токена БЕЗ проверки is_active.
    Используется для redeem_code и link_boosty — чтобы заблокированный
    пользователь мог активировать доступ."""
    user_id = _parse_bearer_user_id(authorization)

    # Только проверка что пользователь существует
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        )
        if not await row.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
    finally:
        await db.close()

    return user_id
