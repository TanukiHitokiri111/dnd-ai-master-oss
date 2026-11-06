"""Payment routes: YooKassa create, webhook, guest purchases, code lookup."""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query

from app.config import settings
from app.db import get_db
from app.db.txn import immediate_txn
from app.deps import get_current_user
from app.models import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentWebhookResponse,
    PaymentStatusResponse,
    GuestPurchaseRequest,
    GuestCodeResponse,
)
from app.services.yookassa import (
    create_payment,
    create_guest_payment,
    verify_webhook,
    parse_webhook_event,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

_GUEST_STATUS_MAP = {
    "completed": "activated",
    "awaiting_registration": "activate_after_register",
}


def _require_yookassa() -> None:
    """Единая проверка конфигурации YooKassa (503, если ключи не заданы)."""
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        raise HTTPException(status_code=503, detail="YooKassa not configured")


def _parse_iso_utc(value: str) -> datetime:
    """Парсинг ISO-даты подписки из БД → aware-UTC datetime (сбои → now).

    Общий для _extend_subscription_txn и /status: формат '...Z' или наивный ISO.
    """
    now = datetime.now(timezone.utc)
    try:
        expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return now
    return expires


async def _record_payment(
    db, sql: str, row_to_params: Callable,
    *, create_fn, create_kwargs: dict,
) -> PaymentCreateResponse:
    """Общий флоу создания платежа: вызов YooKassa → INSERT pending → ответ.

    Разница auth/guest — только вызов yookassa (create_fn + kwargs), SQL
    сохранения и параметры (row_to_params(result) → tuple для INSERT).
    Ошибка создания возвращается как ok=False (НЕ HTTPException — так было
    в оригинальных эндпоинтах).
    """
    result = await create_fn(**create_kwargs)
    if result["error"]:
        logger.error("Payment creation failed: %s", result["error"])
        return PaymentCreateResponse(ok=False, error=result["error"])

    await db.execute(sql, row_to_params(result))
    await db.commit()
    return PaymentCreateResponse(
        ok=True,
        payment_id=result["payment_id"],
        confirmation_url=result["confirmation_url"],
        amount_rub=result["amount_rub"],
    )


# ─── Auth payments (logged in) ───

@router.post("/create", response_model=PaymentCreateResponse)
async def create(request: Request, body: PaymentCreateRequest, user_id: str = Depends(get_current_user)):
    """Create a YooKassa payment for N days."""
    _require_yookassa()

    db = await get_db()
    try:
        user = await db.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
        row = await user.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return await _record_payment(
            db,
            """INSERT INTO payments (payment_id, user_id, amount_rub, days, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', datetime('now'))""",
            row_to_params=lambda r: (r["payment_id"], user_id, r["amount_rub"], body.days),
            create_fn=create_payment,
            create_kwargs=dict(
                shop_id=settings.yookassa_shop_id,
                secret_key=settings.yookassa_secret_key,
                user_id=user_id,
                days=body.days,
                return_url=settings.yookassa_return_url,
                idempotency_key=str(uuid.uuid4()),
            ),
        )
    finally:
        await db.close()


# ─── Guest purchase (no auth) ───

@router.post("/guest-purchase", response_model=PaymentCreateResponse)
async def guest_purchase(body: GuestPurchaseRequest, request: Request):
    """Создать платёж для гостя (без авторизации). 200₽ = эпик навсегда."""
    _require_yookassa()

    db = await get_db()
    try:
        return await _record_payment(
            db,
            """INSERT INTO guest_purchases (payment_id, username, code, status)
               VALUES (?, ?, '', 'pending')""",
            row_to_params=lambda r: (r["payment_id"], body.username),
            create_fn=create_guest_payment,
            create_kwargs=dict(
                shop_id=settings.yookassa_shop_id,
                secret_key=settings.yookassa_secret_key,
                username=body.username,
                return_url=f"{settings.yookassa_return_url}?mode=guest",
                idempotency_key=str(uuid.uuid4()),
            ),
        )
    finally:
        await db.close()


@router.get("/guest-code", response_model=GuestCodeResponse)
async def guest_code(payment_id: str = Query(...)):
    """Проверить статус гостевой покупки."""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT status FROM guest_purchases WHERE payment_id = ?",
            (payment_id,),
        )
        result = await row.fetchone()
        if not result:
            return GuestCodeResponse(status="not_found")
        return GuestCodeResponse(
            status=_GUEST_STATUS_MAP.get(result["status"], "pending")
        )
    finally:
        await db.close()


# ─── Webhook ───

@router.post("/webhook", response_model=PaymentWebhookResponse)
async def webhook(request: Request):
    """Receive YooKassa webhook — payment.succeeded event."""
    _require_yookassa()

    body = await request.body()
    signature = request.headers.get("YooKassa-Signature", "")

    logger.info("Webhook: sig=%.30s... body_len=%d keys=%s body_preview=%s",
                signature, len(body),
                [k for k in request.headers.keys()],
                body[:80])

    if not settings.yookassa_test_mode:
        if not signature:
            logger.warning("Webhook without signature — rejected")
            raise HTTPException(status_code=403, detail="Missing signature")
        if not verify_webhook(body, signature, settings.yookassa_secret_key):
            logger.warning("Invalid webhook signature: sig=%.50s", signature)
            raise HTTPException(status_code=403, detail="Invalid signature")

    event = parse_webhook_event(body)
    if not event:
        return PaymentWebhookResponse(ok=False)

    # ── Guest purchase ──
    if event.get("is_guest"):
        return await _handle_guest_webhook(event)

    # ── Regular auth purchase ──
    return await _handle_auth_webhook(event)


async def _extend_subscription_txn(
    db, lookup_sql: str, lookup_params: tuple,
    *, tier: str, days: int,
) -> dict | None:
    """Атомарное продление подписки ВНУТРИ открытой транзакции (BEGIN IMMEDIATE).

    Читает subscription_expires, продлевает от max(now, expires), пишет UPDATE.
    Возвращает {"user_id", "new_expires", "was_active"} или None, если юзер не найден.
    Вызывается из _handle_guest_webhook и _handle_auth_webhook — общий код
    продления (чтение expires → clamp → +days → UPDATE), различие только в
    способе поиска пользователя и tier.
    """
    row_cur = await db.execute(lookup_sql, lookup_params)
    row = await row_cur.fetchone()
    if not row:
        return None

    now = datetime.now(timezone.utc)
    current_expires = _parse_iso_utc(row["subscription_expires"]) if row["subscription_expires"] else now
    if current_expires < now:
        current_expires = now

    new_expires = current_expires + timedelta(days=days)

    await db.execute(
        """UPDATE users SET is_active = 1, subscription_tier = ?,
           subscription_expires = ? WHERE id = ?""",
        (tier, new_expires.isoformat(), row["id"]),
    )
    return {"user_id": row["id"], "new_expires": new_expires, "was_active": bool(row["is_active"]) if "is_active" in row.keys() else True}


async def _handle_guest_webhook(event: dict) -> PaymentWebhookResponse:
    """Обработать вебхук гостевой покупки: автоактивация пользователя по username."""
    payment_id = event["payment_id"]
    username = event["username"]

    db = await get_db()
    try:
        try:
            async with immediate_txn(db):
                # Идемпотентность ВНУТРИ транзакции: ретрай YooKassa не должен
                # начислить подписку дважды (double credit)
                cur = await db.execute(
                    "SELECT status, username FROM guest_purchases WHERE payment_id = ?",
                    (payment_id,),
                )
                gp = await cur.fetchone()
                if gp and gp["status"] == "completed":
                    logger.info("Guest webhook %s replay ignored (already completed)", payment_id)
                    return PaymentWebhookResponse(ok=True)

                # Ищем пользователя по username
                extended = await _extend_subscription_txn(
                    db,
                    "SELECT id, subscription_expires FROM users WHERE username = ?",
                    (username,),
                    tier="epic", days=30,
                )

                if extended:
                    await db.execute(
                        """UPDATE guest_purchases SET status = 'completed',
                           completed_at = datetime('now') WHERE payment_id = ?""",
                        (payment_id,),
                    )
                    logger.info("Guest purchase %s: user '%s' activated as epic", payment_id, username)
                    return PaymentWebhookResponse(ok=True, user_id=extended["user_id"])

                # Пользователь ещё не зарегистрирован — сохраняем pending с флагом
                await db.execute(
                    """UPDATE guest_purchases SET status = 'awaiting_registration',
                       completed_at = datetime('now') WHERE payment_id = ?""",
                    (payment_id,),
                )
                logger.info("Guest purchase %s: username '%s' not found, awaiting registration", payment_id, username)
                return PaymentWebhookResponse(ok=True)
        except Exception:
            logger.exception("Failed to handle guest webhook")
            return PaymentWebhookResponse(ok=False)
    finally:
        await db.close()


async def _handle_auth_webhook(event: dict) -> PaymentWebhookResponse:
    """Обработать вебхук авторизованной покупки."""
    user_id = event["user_id"]
    days = event["days"]
    payment_id = event["payment_id"]

    db = await get_db()
    try:
        async with immediate_txn(db):
            # Идемпотентность: проверяем rowcount
            cur = await db.execute(
                """UPDATE payments SET status = 'completed', updated_at = datetime('now')
                   WHERE payment_id = ? AND status = 'pending'""",
                (payment_id,),
            )
            if cur.rowcount == 0:
                logger.info("Webhook %s replay ignored (already completed)", payment_id)
                return PaymentWebhookResponse(ok=True)

            existing = await _extend_subscription_txn(
                db,
                "SELECT id, subscription_expires FROM users WHERE id = ?",
                (user_id,),
                tier="tier1", days=days,
            )
            if not existing:
                # Пользователь из платежа не найден — платёж остаётся completed,
                # но продлевать некому (раньше было бы AttributeError на row=None)
                logger.error("Webhook %s: user %s not found, subscription not extended", payment_id, user_id[:8])
                return PaymentWebhookResponse(ok=False)

            new_expires = existing["new_expires"]
            logger.info("Payment %s: user %s +%d days, expires %s", payment_id, user_id[:8], days, new_expires)

            return PaymentWebhookResponse(
                ok=True,
                user_id=user_id,
                days_added=days,
                new_expires=new_expires.isoformat(),
            )
    finally:
        await db.close()


# ─── Status ───

@router.get("/status", response_model=PaymentStatusResponse)
async def status(request: Request, user_id: str = Depends(get_current_user)):
    """Get current payment tier status."""
    db = await get_db()
    try:
        row = await db.execute(
            """SELECT subscription_tier, subscription_expires,
               datetime(subscription_expires) > datetime('now') AS active
               FROM users WHERE id = ?""",
            (user_id,),
        )
        user = await row.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        days_left = 0
        if user["active"] and user["subscription_expires"]:
            delta = _parse_iso_utc(user["subscription_expires"]) - datetime.now(timezone.utc)
            days_left = max(0, delta.days)

        return PaymentStatusResponse(
            tier=user["subscription_tier"] or "free",
            expires_at=user["subscription_expires"] or "",
            days_left=days_left,
        )
    finally:
        await db.close()
