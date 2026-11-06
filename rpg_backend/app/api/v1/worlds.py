"""API: список миров мультивселенной + детальная информация о мире."""
import json
import os
from fastapi import APIRouter, HTTPException

from app.knowledge.worlds import WORLD_TEMPLATES, flow_tier_name
from app.knowledge.srd_rules import (
    SUBCLASS_OPTIONS, BACKGROUNDS,
)
from app.api.v1.world_catalog import (
    visible_race_names, visible_class_names, build_race_entries, build_class_entries,
)

_DESC_PATH = "/app/data/world_descriptions.json"
_IMG_PATH = "/app/data/world_images.json"
_EQUIPMENT_PATH = "/app/data/world_equipment.json"
_MAPS_PATH = "/app/data/world_maps.json"
_LANGUAGES_PATH = "/app/data/world_languages.json"
_BACKGROUNDS_PATH = "/app/data/world_backgrounds.json"
_SKILLS_PATH = "/app/data/world_skills.json"

router = APIRouter(tags=["worlds"])


def _load_world_json(path: str, world_key: str, default):
    """Синхронное чтение JSON-данных мира из файловой системы.

    Возвращает default, если файла нет или ключа мира в нём нет.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default
    return data.get(world_key, default)


@router.get("/worlds")
async def list_worlds():
    """Список всех миров с описаниями, тиром и плотностью магии."""
    worlds = []
    for key, w in sorted(
        WORLD_TEMPLATES.items(),
        key=lambda kv: (-kv[1].tier, kv[0]),
    ):
        worlds.append({
            "key": key,
            "name": w.name,
            "tier": w.tier,
            "tier_name": flow_tier_name(w.tier),
            "magic_density": w.magic_density,
            "tech_level": w.tech_level,
            "genre": w.genre,
            "description": w.description,
            "rules_overrides": w.rules_overrides,
        })
    return {"worlds": worlds}


@router.get("/characters/worlds/{world_key}")
async def get_world_detail(world_key: str):
    """Детальная информация о мире: шаблон + расы + классы + подклассы + бэкграунды."""
    template = WORLD_TEMPLATES.get(world_key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Мир '{world_key}' не найден")

    # --- Расы (общий конструктор из world_catalog) ---
    races = build_race_entries(visible_race_names(world_key), world_key)

    # --- Классы (единый конструктор: имя plain, данные по world-ключу) ---
    class_names = visible_class_names(world_key)
    classes = build_class_entries(class_names, world_key)

    # --- Подклассы (только для классов этого мира) ---
    subclasses = {}
    for cls_name in class_names:
        if cls_name in SUBCLASS_OPTIONS:
            subclasses[cls_name] = SUBCLASS_OPTIONS[cls_name]

    # --- Бэкграунды (все) ---
    backgrounds = []
    for bg_name, bg_data in BACKGROUNDS.items():
        backgrounds.append({
            "name": bg_name,
            "skills": bg_data.get("skills", []),
            "tools": bg_data.get("tools", []),
            "chars": bg_data.get("chars", ""),
            "feature": bg_data.get("feat", ""),
            "feature_desc": "",
            "flavor": bg_data.get("flavor", ""),
        })

    return {
        "world": {
            "key": template.key,
            "name": template.name,
            "tier": template.tier,
            "tier_name": flow_tier_name(template.tier),
            "magic_density": template.magic_density,
            "tech_level": template.tech_level,
            "genre": template.genre,
            "description": template.description,
            "rules_overrides": template.rules_overrides,
        },
        "races": races,
        "classes": classes,
        "subclasses": subclasses,
        "backgrounds": backgrounds,
    }


@router.get("/worlds/content")
async def get_world_content():
    """Атмосферные описания миров + особенности + правила + картинки."""
    result = {"features": {}, "descriptions": {}, "rules": {}, "images": {}}
    
    if os.path.exists(_DESC_PATH):
        with open(_DESC_PATH, encoding="utf-8") as f:
            desc_data = json.load(f)
            result["features"] = desc_data.get("features", {})
            result["descriptions"] = desc_data.get("descriptions", {})
            result["rules"] = desc_data.get("rules", {})
    
    if os.path.exists(_IMG_PATH):
        with open(_IMG_PATH, encoding="utf-8") as f:
            result["images"] = json.load(f)
    
    return result


# ─── World-specific data: equipment / map / languages / backgrounds / skills ───

@router.get("/worlds/{world_key}/equipment")
async def get_world_equipment(world_key: str):
    """Предметы снаряжения мира. Пустой массив, если файла или ключа нет."""
    return _load_world_json(_EQUIPMENT_PATH, world_key, [])


@router.get("/worlds/{world_key}/map")
async def get_world_map(world_key: str):
    """Карта мира: регионы, столица, локации. Пустой словарь, если данных нет."""
    return _load_world_json(_MAPS_PATH, world_key, {})


@router.get("/worlds/{world_key}/languages")
async def get_world_languages(world_key: str):
    """Языки мира с привязкой к расам. Пустой массив, если данных нет."""
    return _load_world_json(_LANGUAGES_PATH, world_key, [])


@router.get("/worlds/{world_key}/backgrounds")
async def get_world_backgrounds(world_key: str):
    """Предыстории мира по расам: {раса: [предыстории]}. Пустой словарь, если данных нет."""
    return _load_world_json(_BACKGROUNDS_PATH, world_key, {})


@router.get("/worlds/{world_key}/skills")
async def get_world_skills(world_key: str):
    """Уникальные навыки мира. Пустой массив, если данных нет."""
    return _load_world_json(_SKILLS_PATH, world_key, [])