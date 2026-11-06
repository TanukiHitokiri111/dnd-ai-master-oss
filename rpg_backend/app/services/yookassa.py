"""YooKassa payment service: create payments, verify webhooks, guest purchases."""

import logging
import hashlib
import hmac
import json
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3"
PRICE_PER_DAY_RUB = 7


async def _create_yookassa_payment(
    shop_id: str,
    secret_key: str,
    payload: dict,
    idempotency_key: str,
    *,
    context: str,
) -> dict:
    """Единый POST /payments для YooKassa (общий движок create_payment/create_guest_payment).

    Возвращает: {"payment_id": str, "confirmation_url": str, "amount_rub": int, "error": str|None}
    """
    # Служебное поле (не часть API YooKassa) — забираем до отправки
    amount_rub = payload.pop("amount_value_rub", 0)

    auth = httpx.BasicAuth(shop_id, secret_key)
    headers = {
        "Idempotence-Key": idempotency_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{YOOKASSA_API}/payments",
                json=payload,
                auth=auth,
                headers=headers,
            )
            data = resp.json()

            if resp.status_code == 200 or resp.status_code == 201:
                return {
                    "payment_id": data["id"],
                    "confirmation_url": data["confirmation"]["confirmation_url"],
                    "amount_rub": amount_rub,
                    "error": None,
                }
            else:
                err = data.get("description", data.get("type", f"HTTP {resp.status_code}"))
                logger.error("YooKassa %s failed: %s", context, err)
                return {"payment_id": "", "confirmation_url": "", "amount_rub": 0, "error": err}

        except Exception as e:
            logger.exception("YooKassa %s exception", context)
            return {"payment_id": "", "confirmation_url": "", "amount_rub": 0, "error": str(e)}


def _yookassa_payload(amount_rub: int, description: str, metadata: dict, return_url: str) -> dict:
    """Собрать тело запроса платежа (общий формат для auth и guest платежей)."""
    return {
        "amount": {
            "value": f"{amount_rub:.2f}",
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "description": description,
        "metadata": metadata,
        # служебное поле для _create_yookassa_payment (удаляется перед отправкой)
        "amount_value_rub": amount_rub,
    }


async def create_payment(
    shop_id: str,
    secret_key: str,
    user_id: str,
    days: int,
    return_url: str,
    idempotency_key: str,
) -> dict:
    """Create a payment via YooKassa API.

    Returns: {"payment_id": str, "confirmation_url": str, "amount": int, "error": str|None}
    """
    amount_rub = days * PRICE_PER_DAY_RUB
    payload = _yookassa_payload(
        amount_rub,
        f"D&D AI Master — {days} дн. ({amount_rub}₽)",
        {"user_id": user_id, "days": str(days)},
        return_url,
    )
    return await _create_yookassa_payment(shop_id, secret_key, payload, idempotency_key, context="create_payment")


async def create_guest_payment(
    shop_id: str,
    secret_key: str,
    username: str,
    return_url: str,
    idempotency_key: str,
) -> dict:
    """Создать платёж для гостевой покупки (без авторизации).
    Возвращает: {"payment_id": str, "confirmation_url": str, "amount_rub": int, "error": str|None}
    """
    amount_rub = 200
    payload = _yookassa_payload(
        amount_rub,
        "D&D AI Master — Подписка Эпик (200₽/мес)",
        {"guest_purchase": "1", "username": username, "product": "epic"},
        return_url,
    )
    return await _create_yookassa_payment(shop_id, secret_key, payload, idempotency_key, context="create_guest_payment")


def verify_webhook(body: bytes, signature_header: str, secret_key: str) -> bool:
    """Verify YooKassa webhook HMAC signature."""
    if not signature_header or not body:
        return False

    try:
        expected = hmac.new(
            secret_key.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        logger.exception("YooKassa webhook verification failed")
        return False


def parse_webhook_event(body: bytes) -> Optional[dict]:
    """Parse webhook body, return {"event": str, "payment_id": str, "user_id": str, "days": int, "is_guest": bool, "username": str} or None."""
    try:
        data = json.loads(body)
        event = data.get("event", "")
        payment = data.get("object", {})

        if event != "payment.succeeded":
            return None

        if payment.get("status") != "succeeded":
            return None

        metadata = payment.get("metadata", {})
        
        # Guest purchase?
        if metadata.get("guest_purchase") == "1":
            username = metadata.get("username", "")
            if not username:
                logger.warning("Guest purchase without username")
                return None
            return {
                "event": event,
                "payment_id": payment["id"],
                "is_guest": True,
                "username": username,
                "amount": payment.get("amount", {}),
            }

        # Regular auth purchase
        user_id = metadata.get("user_id", "")
        days = int(metadata.get("days", "0"))

        if not user_id or days <= 0:
            logger.warning("Invalid webhook metadata: user_id=%s days=%s", user_id, days)
            return None

        return {
            "event": event,
            "payment_id": payment["id"],
            "is_guest": False,
            "user_id": user_id,
            "days": days,
            "amount": payment.get("amount", {}),
        }
    except Exception:
        logger.exception("Failed to parse YooKassa webhook")
        return None
