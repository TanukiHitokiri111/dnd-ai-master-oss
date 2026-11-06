"""Character API: SRD справочные эндпоинты."""


from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.knowledge.srd_rules import BACKGROUNDS, CLASS_STARTING_EQUIPMENT, ITEM_CATALOG, RACIAL_SUBRACES, CLASS_FEATURES_L1, CLASS_PROFICIENCIES, CLASS_HIT_DIE, CLASS_DESCRIPTIONS, CLASS_FLAVORS, SPELLS_BY_CLASS, SKILL_LIST, SKILL_NAMES_RU, SKILL_FLAVOR, SPELL_FLAVOR, SUBCLASS_OPTIONS
from app.api.v1.world_catalog import (
    visible_race_names, visible_class_names, build_race_entries, build_class_entries,
)
from app.models import SrdBackgroundsResponse, SrdClassesResponse, SrdRacesResponse, SrdEquipmentResponse, SrdSpellsResponse


router = APIRouter(tags=["characters"])

@router.get("/srd/backgrounds", response_model=SrdBackgroundsResponse)
async def list_backgrounds():
    """Список всех предысторий с деталями."""
    return {"backgrounds": [
        {
            "name": name,
            "skills": data["skills"],
            "tools": data["tools"],
            "chars": data["chars"],
            "feature": data["feat"],
            "feature_desc": "",
            "flavor": data.get("flavor", ""),
        }
        for name, data in BACKGROUNDS.items()
    ]}


@router.get("/srd/classes", response_model=SrdClassesResponse)
async def list_classes(world: str = ""):
    """Список классов с владениями и умениями 1-го уровня. ?world= — фильтр по миру."""
    return {"classes": build_class_entries(visible_class_names(world or None), world or None)}


@router.get("/srd/races", response_model=SrdRacesResponse)
async def list_races(brief: bool = False, world: str = ""):
    """Список рас с чертами, бонусами и подрасами. ?brief=true — только названия и описания без trait'ов. ?world= — фильтр по миру."""
    return {"races": build_race_entries(visible_race_names(world or None), world or None, brief=brief)}


@router.get("/srd/subraces")
async def list_subraces(race: str = ""):
    """Список подрас. Если указана раса — только для неё, иначе все."""
    if race:
        if race in RACIAL_SUBRACES:
            return RACIAL_SUBRACES[race]
        return {"label": "", "flavor": "", "subraces": []}
    return RACIAL_SUBRACES


@router.get("/srd/subclasses")
async def list_subclasses(class_name: str = ""):
    """Список специализаций. Если указан класс — только для него, иначе все."""
    if class_name:
        if class_name in SUBCLASS_OPTIONS:
            return SUBCLASS_OPTIONS[class_name]
        return {"label": "", "flavor": "", "options": []}
    return SUBCLASS_OPTIONS


@router.get("/srd/equipment", response_model=SrdEquipmentResponse)
async def list_equipment():
    """Каталог предметов."""
    # Группируем по типам
    by_type: dict[str, list] = {}
    for key, item in ITEM_CATALOG.items():
        t = item["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append({"key": key, **item})
    return {"equipment": by_type}


@router.get("/srd/spells", response_model=SrdSpellsResponse)
async def list_spells(class_name: str = ""):
    """Список заклинаний (опционально фильтр по классу)."""
    if class_name and class_name in SPELLS_BY_CLASS:
        spells = SPELLS_BY_CLASS[class_name]
    else:
        # Все заклинания
        all_spells = []
        for spells in SPELLS_BY_CLASS.values():
            for s in spells:
                if s["key"] not in {x["key"] for x in all_spells}:
                    all_spells.append(s)
        spells = all_spells
    # Инжектим flavour
    enriched = []
    for s in spells:
        s = dict(s)
        s["flavor"] = SPELL_FLAVOR.get(s.get("key", ""), "")
        enriched.append(s)
    return {"spells": enriched}


@router.get("/srd/skills")
async def list_skills():
    """Список навыков с описаниями."""
    return {"skills": [
        {"key": k, "name": SKILL_NAMES_RU.get(k, k), "flavor": SKILL_FLAVOR.get(k, "")}
        for k in SKILL_LIST
    ]}


# ──────────────────────────────────────────────
# MIXED HERITAGE: config + roll
# ──────────────────────────────────────────────

class MixedHeritageRollRequest(BaseModel):
    species_percentages: dict[str, int] = Field(..., description="{\"Раса\": процент}")
    seed: int | None = Field(None, description="Опциональное зерно для воспроизводимости")


EXTRA_ITEM_CATALOG_LEGACY_PLACEHOLDER = None  # noqa: E501
