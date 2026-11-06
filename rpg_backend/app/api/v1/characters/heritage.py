"""Character API: смешанное наследие."""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.knowledge.srd_rules import MIXED_HERITAGE_CONFIG, COMPAT_RULES
from app.services.heritage_roller import roll_mixed_heritage, get_compatible_races, check_compatibility


router = APIRouter(tags=["characters"])

class MixedHeritageRollRequest(BaseModel):
    species_percentages: dict[str, int] = Field(..., description="{\"Раса\": процент}")
    seed: int | None = Field(None, description="Опциональное зерно для воспроизводимости")


@router.get("/characters/mixed-heritage/config")
async def get_mixed_heritage_config():
    """Возвращает расы, доступные для смешивания, с информацией о совместимости."""
    species_list = []
    for race_name in sorted(MIXED_HERITAGE_CONFIG.keys()):
        if race_name == "Смешанная":
            continue  # «Смешанная» не участвует в выборе процентов
        rule = COMPAT_RULES.get(race_name, {})
        species_list.append({
            "name": race_name,
            "can_mix": rule.get("can_mix", True),
            "group": rule.get("group", "unknown"),
            "compatible_with": rule.get("compatible_with", []),
            "speed": MIXED_HERITAGE_CONFIG[race_name].get("speed", 30),
            "size": MIXED_HERITAGE_CONFIG[race_name].get("size_category", "medium"),
        })
    return {"species": species_list}


@router.get("/characters/mixed-heritage/compatible/{race_name}")
async def get_compatible_species(race_name: str):
    """Возвращает список рас, совместимых с данной для смешанного наследия."""
    compat = get_compatible_races(race_name)
    rule = COMPAT_RULES.get(race_name, {})
    return {
        "race": race_name,
        "can_mix": rule.get("can_mix", False),
        "group": rule.get("group", "unknown"),
        "compatible_with": compat,
    }


@router.post("/characters/mixed-heritage/check")
async def check_mixed_compatibility(data: MixedHeritageRollRequest):
    """Проверяет совместимость набора рас."""
    races = list(data.species_percentages.keys())
    errors = check_compatibility(races)
    return {"compatible": len(errors) == 0, "errors": errors}


@router.post("/characters/mixed-heritage/roll")
async def roll_heritage(data: MixedHeritageRollRequest):
    """Бросок смешанного наследия."""
    try:
        return roll_mixed_heritage(data.species_percentages, seed=data.seed)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
