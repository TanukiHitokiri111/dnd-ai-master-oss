"""Character API: лут."""


from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user
from app.knowledge.loot_tables import generate_loot, detect_biome_from_text
from app.models import LootRequest, LootResponse

from app.api.v1.character_helpers import _get_char

router = APIRouter(tags=["characters"])

@router.post("/characters/{char_id}/loot", response_model=LootResponse)
async def generate_loot_for_character(
    char_id: str,
    data: LootRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Сгенерировать лут-дроп на основе биома или текста сцены.
    Предметы сразу сохраняются в инвентарь персонажа.
    """
    db = await get_db()
    try:
        await _get_char(db, char_id, user_id)

        # Определяем биом
        biome = data.biome
        if not biome and data.scene_text:
            biome = detect_biome_from_text(data.scene_text)
        if not biome:
            biome = "dungeon"  # default

        # Валидация: не больше 100 предметов за раз
        count = min(data.count, 100)
        # Генерируем предметы
        loot_items = generate_loot(biome, count)

        # Сохраняем в БД и собираем ответ
        import json as _json
        saved_items = []
        for item in loot_items:
            mods = item.get("modifiers", {})
            cursor = await db.execute(
                """INSERT INTO items (character_id, item_key, item_name, item_type, item_subtype, qty, slot, equipped, attunement, notes, modifiers, flavor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    char_id,
                    item["item_key"],
                    item["item_name"],
                    item["item_type"],
                    item["item_subtype"],
                    item["qty"],
                    item["slot"],
                    item.get("equipped", 0),
                    item.get("attunement", 0),
                    item.get("notes", "Найдено"),
                    _json.dumps(mods, ensure_ascii=False),
                    mods.get("flavor", "") if isinstance(mods, dict) else "",
                ),
            )
            item_id = cursor.lastrowid
            saved_items.append({
                "id": item_id,
                "item_key": item["item_key"],
                "item_name": item["item_name"],
                "item_type": item["item_type"],
                "item_subtype": item["item_subtype"],
                "qty": item["qty"],
                "modifiers": mods,
                "flavor": mods.get("flavor", "") if isinstance(mods, dict) else "",
            })

        # Атомарно: все предметы одним коммитом (обрыв цикла не оставит частичный лут)
        await db.commit()

        from app.knowledge.loot_tables import LOOT_TABLES
        biome_name = LOOT_TABLES.get(biome, {}).get("name", biome)

        return LootResponse(
            biome=biome,
            biome_name=biome_name,
            items=saved_items,
        )

    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()



# =============================================================================
# LEVEL-UP — повышение уровня и мультикласс
# =============================================================================

