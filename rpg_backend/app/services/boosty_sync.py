"""Boosty subscriber sync: fetch subscribers from Boosty API → update D&D tiers."""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.db import get_db

logger = logging.getLogger(__name__)

BOOSTY_API = "https://api.boosty.to/v1"

TIER_MAP = {
    "Follower": "free",
    "1 уровень": "tier1",
    "Уровень 2": "tier2",
    "Уровень 20 нахер": "tier3",
}


async def fetch_all_subscribers(token: str) -> list[dict]:
    """Fetch ALL subscribers from the Boosty blog set in BOOSTY_BLOG."""
    headers = {"Authorization": f"Bearer {token}"}
    subscribers = []
    offset = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            url = f"{BOOSTY_API}/blog/{settings.boosty_blog}/subscribers"
            params = {"limit": 50, "offset": offset}

            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    logger.warning("Boosty API returned %d at offset %d", resp.status_code, offset)
                    break
                data = resp.json()
            except Exception as e:
                logger.error("Boosty API fetch failed at offset %d: %s", offset, e)
                break

            batch = data.get("data", [])
            subscribers.extend(batch)
            if len(batch) < 50:
                break
            offset += 50

    logger.info("Fetched %d Boosty subscribers", len(subscribers))
    return subscribers


def _match_subscriber_to_user(sub: dict, boosty_login: str) -> bool:
    """Check if this Boosty subscriber matches a D&D user's boosty_login."""
    if not boosty_login:
        return False
    login_lower = boosty_login.strip().lower()
    if not login_lower:
        return False

    sub_name = (sub.get("name") or "").strip().lower()
    sub_email = (sub.get("email") or "").strip().lower()

    # Exact match only on name or email
    if login_lower == sub_name or login_lower == sub_email:
        return True

    return False


async def sync_boosty_subscribers(token: str | None = None) -> dict:
    """Sync Boosty subscribers → D&D users subscription_tier."""
    if not token:
        token = settings.boosty_api_token
    if not token:
        return {"error": "BOOSTY_API_TOKEN not configured in .env"}

    subscribers = await fetch_all_subscribers(token)

    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        rows = await db.execute(
            "SELECT id, username, boosty_login, subscription_tier FROM users "
            "WHERE boosty_login != '' AND is_active = 1"
        )
        dnd_users = await rows.fetchall()
        logger.info("Found %d D&D users with boosty_login", len(dnd_users))

        if not dnd_users:
            await db.rollback()
            return {
                "synced": 0,
                "subscribers": len(subscribers),
                "note": "No D&D users with boosty_login",
            }

        updates = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        for user in dnd_users:
            matched = None
            for sub in subscribers:
                if _match_subscriber_to_user(sub, user["boosty_login"]):
                    matched = sub
                    break

            if matched:
                level_name = (matched.get("level") or {}).get("name", "")
                tier = TIER_MAP.get(level_name, "free")

                is_paid = tier not in ("free", "")
                if tier != user["subscription_tier"] or is_paid:
                    if is_paid:
                        await db.execute(
                            "UPDATE users SET subscription_tier = ?, subscription_expires = ?, is_active = 1 WHERE id = ?",
                            (tier, expires, user["id"]),
                        )
                    elif tier != user["subscription_tier"]:
                        # tier изменился на free — только обновляем tier, expires не трогаем
                        await db.execute(
                            "UPDATE users SET subscription_tier = ? WHERE id = ?",
                            (tier, user["id"]),
                        )
                    updates.append({
                        "user_id": user["id"],
                        "username": user["username"],
                        "boosty_login": user["boosty_login"],
                        "tier_old": user["subscription_tier"],
                        "tier_new": tier,
                    })
                    logger.info("Synced %s (%s): %s → %s",
                        user["username"], user["boosty_login"],
                        user["subscription_tier"] or "none", tier)
                else:
                    logger.debug("Unchanged %s: tier stays %s", user["username"], tier)
            else:
                logger.debug("No match for %s (boosty_login=%s)",
                    user["username"], user["boosty_login"])

        await db.commit()
        return {
            "synced": len(updates),
            "subscribers": len(subscribers),
            "dnd_users_checked": len(dnd_users),
            "updates": updates,
        }
    finally:
        await db.close()
