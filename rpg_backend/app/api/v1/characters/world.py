"""Character API: мир: квесты и карта."""

import json

from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import get_current_user

from app.api.v1.character_helpers import _get_char

router = APIRouter(tags=["characters"])

@router.get("/characters/{char_id}/quests")
async def list_quests(char_id: str, user_id: str = Depends(get_current_user)):
    """Получить все квесты персонажа."""
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)
        cur = await db.execute(
            "SELECT id, quest_key, title, description, status, objectives, rewards, source_npc, created_at, updated_at FROM quests WHERE character_id = ? ORDER BY status, id LIMIT 1000",
            (char_id,),
        )
        rows = await cur.fetchall()
        return [{
            "id": r[0], "quest_key": r[1], "title": r[2], "description": r[3],
            "status": r[4], "objectives": json.loads(r[5]) if r[5] else [],
            "rewards": json.loads(r[6]) if r[6] else {},
            "source_npc": r[7], "created_at": r[8], "updated_at": r[9],
        } for r in rows]
    finally:
        await db.close()


@router.get("/characters/{char_id}/map")
async def get_world_map(char_id: str, user_id: str = Depends(get_current_user)):
    """Карта мира: открытые локации + соседи + текущая локация.

    Возвращает: {current: str, discovered: [{key, name, desc, region, neighbors}],
    all_cities: [{key, name}]} — discovered только те, что персонаж открыл
    через [TRAVEL: город].
    """
    from app.knowledge.worlds import WORLD_MAP, nearest_cities

    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)
        cur = await db.execute(
            "SELECT location, discovered_locations FROM game_state WHERE user_id = ? AND character_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id, char_id),
        )
        row = await cur.fetchone()
        discovered = []
        if row and row["discovered_locations"]:
            try:
                discovered = json.loads(row["discovered_locations"])
            except Exception:
                discovered = []

        # Текущая локация — сопоставляем с WORLD_MAP
        current_key = ""
        current_name = row["location"] if row and row["location"] else ""
        for k, v in WORLD_MAP.items():
            if v["name"].lower() == (current_name or "").lower():
                current_key = k
                break

        discovered_out = []
        for key in discovered:
            info = WORLD_MAP.get(key)
            if not info:
                continue
            discovered_out.append({
                "key": key,
                "name": info["name"],
                "desc": info["desc"],
                "region": info["region"],
                "neighbors": nearest_cities(key),
            })

        return {
            "current": {"key": current_key, "name": current_name},
            "discovered": discovered_out,
            "all_cities": [{"key": k, "name": v["name"]} for k, v in WORLD_MAP.items()],
        }
    finally:
        await db.close()
