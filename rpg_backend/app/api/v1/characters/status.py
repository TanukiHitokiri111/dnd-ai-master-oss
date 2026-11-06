"""Character API: статус персонажа."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user
from app.knowledge.srd_rules import CASTER_CLASSES, SPELL_SLOTS_BY_LEVEL, SKILL_LIST, SKILL_NAMES_RU, SKILL_FLAVOR, STAT_NAMES_RU

# Модификатор характеристики: (v - 10) // 2
def mod(v: int) -> int:
    return (v - 10) // 2
from app.models import SpellResponse

from app.api.v1.character_helpers import _casting_ability_for_class, _get_char, _get_items, _get_spells, _row_to_char

router = APIRouter(tags=["characters"])

STAT_SKILL_MAP = {
    "acrobatics": "dex", "animal_handling": "wis", "arcana": "int",
    "athletics": "str", "deception": "cha", "history": "int",
    "insight": "wis", "intimidation": "cha", "investigation": "int",
    "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int",
    "sleight_of_hand": "dex", "stealth": "dex", "survival": "wis",
}


@router.get("/characters/{char_id}/status")
async def character_status(char_id: str, user_id: str = Depends(get_current_user)):
    """Полное окно статуса: статы, скиллы, спеллы, слоты."""
    db = await get_db()
    try:
        char = await _get_char(db, char_id, user_id)
        stats = json.loads(char["stats"]) if isinstance(char["stats"], str) else char["stats"]
        skill_profs = json.loads(char["skill_proficiencies"]) if isinstance(char["skill_proficiencies"], str) else char["skill_proficiencies"]
        languages = json.loads(char["languages"]) if isinstance(char["languages"], str) else char["languages"]
        features = json.loads(char["features"]) if isinstance(char["features"], str) else char["features"]
        profs = json.loads(char["proficiencies"]) if isinstance(char["proficiencies"], str) else char["proficiencies"]
        items = await _get_items(db, char_id)
        spells = await _get_spells(db, char_id)

        level = char["level"]
        prof_bonus = next((pb for lvl, pb in sorted(
            [(1,2),(5,3),(9,4),(13,5),(17,6)], reverse=True
        ) if level >= lvl), 2)

        # Скиллы с итоговыми бонусами
        skills_with_bonuses = {}
        for skill_key in SKILL_LIST:
            stat_key = STAT_SKILL_MAP.get(skill_key, "str")
            stat_val = stats.get(stat_key, 10)
            bonus = mod(stat_val)
            if skill_key in skill_profs:
                bonus += prof_bonus
            skills_with_bonuses[skill_key] = {
                "name": SKILL_NAMES_RU.get(skill_key, skill_key),
                "stat": stat_key,
                "stat_name": STAT_NAMES_RU.get(stat_key, stat_key),
                "bonus": bonus,
                "proficient": skill_key in skill_profs,
                "flavor": SKILL_FLAVOR.get(skill_key, ""),
            }

        # Спеллслоты
        class_name = char["class_name"]
        spell_slots = SPELL_SLOTS_BY_LEVEL.get(level, {}) if class_name in CASTER_CLASSES else {}
        casting_ability = _casting_ability_for_class(class_name)
        casting_stat = {"ИНТ": "int", "МУД": "wis", "ХАР": "cha"}.get(casting_ability, "int")
        spell_dc = 8 + prof_bonus + mod(stats.get(casting_stat, 10))
        spell_attack = prof_bonus + mod(stats.get(casting_stat, 10))

        return {
            "character": _row_to_char(char, items),
            "spells": [SpellResponse(**s) for s in spells],
            "spell_slots": spell_slots,
            "spell_dc": spell_dc,
            "spell_attack": spell_attack,
            "casting_ability": casting_ability,
            "skills": skills_with_bonuses,
            "prof_bonus": prof_bonus,
            "saves": {
                s.upper(): mod(stats.get(s, 10)) + (prof_bonus if s in profs.get("saves", []) else 0)
                for s in ["str", "dex", "con", "int", "wis", "cha"]
            },
        }
    except HTTPException:
        raise
    finally:
        await db.close()


# ──────────────────────────────────────────────
# LOOT GENERATION
# ──────────────────────────────────────────────


