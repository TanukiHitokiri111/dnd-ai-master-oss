"""Auth API: регистрация, вход, Boosty + коды доступа."""

import aiosqlite
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import create_token, hash_password, new_id, verify_password
from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_current_user_allow_blocked
from app.logger import logger
from app.models import (
    AuthRequest, AuthResponse, AuthStatusResponse,
    BoostyLinkRequest, LinkBoostyResponse,
    RedeemCodeRequest, RedeemCodeResponse,
)
from app.services import boosty_sync
from app.services.rate_limiter import rate_limiter
from app.exceptions import RateLimitError

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
async def register(data: AuthRequest):
    """Создать нового пользователя."""
    db = await get_db()
    try:
        # Проверяем что username свободен
        row = await db.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        if await row.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким именем уже существует",
            )

        # Если передан boosty_login — проверяем что он не занят
        if data.boosty_login:
            row = await db.execute(
                "SELECT id FROM users WHERE boosty_login = ?",
                (data.boosty_login,),
            )
            if await row.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Boosty-логин уже привязан к другому аккаунту",
                )

        user_id = new_id()
        pwd_hash = hash_password(data.password)
        try:
            await db.execute(
                "INSERT INTO users (id, username, password_hash, boosty_login, is_active) VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    data.username,
                    pwd_hash,
                    data.boosty_login or "",
                    0 if settings.require_access else 1,
                ),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким именем или Boosty-логином уже существует",
            )

        token = create_token(user_id)

        # Проверяем отложенные гостевые покупки
        await _activate_pending_guest_purchases(db, data.username, user_id)

        return AuthResponse(token=token, user_id=user_id)
    finally:
        await db.close()


@router.post("/auth/login", response_model=AuthResponse)
async def login(data: AuthRequest):
    """Войти в существующий аккаунт."""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (data.username,)
        )
        user = await row.fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
            )

        token = create_token(user["id"])
        return AuthResponse(token=token, user_id=user["id"])
    finally:
        await db.close()


@router.post("/auth/link_boosty", response_model=LinkBoostyResponse)
async def link_boosty(data: BoostyLinkRequest, user_id: str = Depends(get_current_user_allow_blocked)):
    """Привязать Boosty-логин к аккаунту. Старый аккаунт деактивируется.
    
    Активный бусти-подписчик получит доступ через периодическую синхронизацию
    (boosty_sync) или вызов sync_boosty_subscribers."""
    db = await get_db()
    try:
        # Проверяем что логин не занят другим пользователем
        row = await db.execute(
            "SELECT id, is_active FROM users WHERE boosty_login = ? AND id != ?",
            (data.boosty_login, user_id),
        )
        old = await row.fetchone()
        old_deactivated = False
        if old:
            # Деактивируем старый аккаунт с этим логином
            await db.execute(
                "UPDATE users SET boosty_login = '', is_active = 0 WHERE id = ?",
                (old["id"],),
            )
            old_deactivated = True

        # Привязываем текущему
        try:
            await db.execute(
                "UPDATE users SET boosty_login = ? WHERE id = ?",
                (data.boosty_login, user_id),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Этот Boosty-логин уже привязан к другому аккаунту",
            )

        logger.info("Boosty login linked: user=%s login=%s old_deactivated=%s",
            user_id[:8], data.boosty_login, old_deactivated)

        return LinkBoostyResponse(ok=True, old_user_deactivated=old_deactivated)
    finally:
        await db.close()


@router.post("/auth/redeem_code", response_model=RedeemCodeResponse)
async def redeem_code(data: RedeemCodeRequest, user_id: str = Depends(get_current_user_allow_blocked)):
    """Активировать код доступа (атомарно, с rate limit)."""
    # Rate limit (общий для redeem)
    try:
        await rate_limiter.check(f"redeem:{user_id}")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Подождите минуту.")

    db = await get_db()
    try:
        # Заранее читаем метаданные кода для точной диагностики
        code_meta = await db.execute(
            "SELECT use_count, max_uses, used_by FROM access_codes WHERE code = ?",
            (data.code,),
        )
        code_info = await code_meta.fetchone()
        if not code_info:
            raise HTTPException(status_code=404, detail="Код не найден")

        # Атомарный UPDATE: проверяем условия в WHERE + проверяем rowcount
        cursor = await db.execute(
            "UPDATE access_codes SET use_count = use_count + 1, used_by = ?, "
            "used_at = datetime('now') "
            "WHERE code = ? "
            "AND use_count < max_uses "
            "AND (max_uses > 1 OR used_by IS NULL)",
            (user_id, data.code),
        )
        if cursor.rowcount == 0:
            # Используем заранее прочитанные данные для точной диагностики
            if code_info["use_count"] >= code_info["max_uses"]:
                raise HTTPException(status_code=410, detail="Код уже использован")
            if code_info["used_by"]:
                raise HTTPException(status_code=410, detail="Код уже активирован")
            raise HTTPException(status_code=410, detail="Код недействителен")

        # Получаем duration_days
        row = await db.execute(
            "SELECT duration_days FROM access_codes WHERE code = ?", (data.code,)
        )
        code_row = await row.fetchone()
        if not code_row:
            raise HTTPException(status_code=404, detail="Код не найден")
        duration = int(code_row["duration_days"])

        # Активируем пользователя (не перезаписываем если уже есть более длинная подписка)
        expires_at_dt = datetime.now(timezone.utc) + timedelta(days=duration)
        expires_at_str = expires_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        await db.execute(
            "UPDATE users SET is_active = 1, subscription_tier = 'tier1', "
            "subscription_expires = CASE "
            "  WHEN subscription_expires = '' THEN ? "
            "  WHEN datetime(subscription_expires) < datetime(?) THEN ? "
            "  ELSE subscription_expires "
            "END "
            "WHERE id = ?",
            (expires_at_str, expires_at_str, expires_at_str, user_id),
        )
        await db.commit()

        logger.info("Redeemed code %s for user %s (%d days)", data.code, user_id[:8], duration)
        return RedeemCodeResponse(ok=True, expires_at=expires_at_str)
    finally:
        await db.close()


@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status(user_id: str = Depends(get_current_user_allow_blocked)):
    """Статус подписки текущего пользователя."""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT boosty_login, subscription_tier, subscription_expires, is_active FROM users WHERE id = ?",
            (user_id,),
        )
        user = await row.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        days_left = 0
        if user["subscription_expires"]:
            try:
                expires = datetime.fromisoformat(user["subscription_expires"])
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                days_left = (expires - now).days
                if days_left < 0:
                    days_left = 0
            except (ValueError, TypeError):
                pass

        return AuthStatusResponse(
            is_active=bool(int(user["is_active"])),
            subscription_tier=user["subscription_tier"] or "",
            subscription_expires=user["subscription_expires"] or "",
            boosty_login=user["boosty_login"] or None,
            days_left=days_left,
        )
    finally:
        await db.close()


async def _activate_pending_guest_purchases(db, username: str, user_id: str) -> None:
    """Если есть отложенная гостевая покупка для этого username — автоактивировать."""
    try:
        row = await db.execute(
            "SELECT payment_id, status FROM guest_purchases "
            "WHERE username = ? AND status = 'awaiting_registration' "
            "ORDER BY completed_at DESC LIMIT 1",
            (username,),
        )
        purchase = await row.fetchone()
        if not purchase:
            return
        # Активируем пользователя как epic на 30 дней
        from datetime import datetime, timedelta, timezone
        expires_dt = datetime.now(timezone.utc) + timedelta(days=30)
        expires = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        await db.execute(
            """UPDATE users SET is_active = 1, subscription_tier = 'epic',
               subscription_expires = ? WHERE id = ?""",
            (expires, user_id),
        )
        await db.execute(
            """UPDATE guest_purchases SET status = 'completed'
               WHERE payment_id = ?""",
            (purchase["payment_id"],),
        )
        await db.commit()  # фиксируем активацию — иначе close() откатит UPDATE
        logger.info(
            "Auto-activated guest purchase %s for user %s (%s)",
            purchase["payment_id"], username, user_id[:8],
        )
    except Exception:
        logger.exception("Failed to activate pending guest purchase for %s", username)
