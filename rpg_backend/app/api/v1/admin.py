"""Admin API: генерация кодов доступа."""

import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import AccessCodeGenerateRequest, GenerateCodesResponse
from app.services import boosty_sync

router = APIRouter(tags=["admin"])


def _is_admin(user_id: str) -> bool:
    """Проверить что user_id в списке админов."""
    admin_ids = [x.strip() for x in settings.admin_user_ids.split(",") if x.strip()]
    return user_id in admin_ids


def _generate_code(prefix: str = "TANUKI") -> str:
    """Сгенерировать код формата PREFIX-XXXX-XXXX."""
    alphabet = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(alphabet) for _ in range(4))
    part2 = ''.join(secrets.choice(alphabet) for _ in range(4))
    return f"{prefix}-{part1}-{part2}"


@router.post("/admin/generate_codes", response_model=GenerateCodesResponse)
async def generate_codes(data: AccessCodeGenerateRequest, user_id: str = Depends(get_current_user)):
    """Сгенерировать коды доступа (только админ)."""
    if not _is_admin(user_id):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        codes = []
        for _ in range(data.count):
            code = _generate_code(data.prefix)
            # Уникальность
            attempts = 0
            while True:
                row = await db.execute("SELECT 1 FROM access_codes WHERE code = ?", (code,))
                if not await row.fetchone():
                    break
                attempts += 1
                if attempts > 10:
                    raise HTTPException(status_code=500, detail="Не удалось сгенерировать уникальный код")
                code = _generate_code(data.prefix)

            await db.execute(
                "INSERT INTO access_codes (code, created_by, duration_days, note) VALUES (?, ?, ?, ?)",
                (code, user_id, data.duration_days, data.note),
            )
            codes.append(code)

        await db.commit()
        return GenerateCodesResponse(codes=codes)
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.get("/admin/codes")
async def list_codes(
    user_id: str = Depends(get_current_user),
    status_filter: str = Query("all", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Список кодов (только админ)."""
    if not _is_admin(user_id):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    db = await get_db()
    try:
        where_clause = ""
        params = []
        ALLOWED_FILTERS = {
            "all": "",
            "unused": "WHERE used_by IS NULL",
            "used": "WHERE used_by IS NOT NULL",
            "expired": "WHERE used_by IS NULL AND datetime(created_at, duration_days || ' days') < datetime('now')",
        }
        where_clause = ALLOWED_FILTERS.get(status_filter, "")

        rows = await db.execute(
            f"SELECT * FROM access_codes {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        codes = [dict(row) for row in await rows.fetchall()]

        count_row = await db.execute(f"SELECT COUNT(*) as cnt FROM access_codes {where_clause}", params)
        total = (await count_row.fetchone())["cnt"]

        return {"codes": codes, "total": total, "limit": limit, "offset": offset}
    finally:
        await db.close()


@router.post("/admin/sync_boosty")
async def sync_boosty(user_id: str = Depends(get_current_user)):
    """Синхронизировать подписки Boosty → D&D (только админ)."""
    if not _is_admin(user_id):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    result = await boosty_sync.sync_boosty_subscribers()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
