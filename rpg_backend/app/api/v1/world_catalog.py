"""Общие конструкторы каталогов рас/классов для SRD-эндпоинтов и деталей мира.

Раньше один и тот же цикл построения описаний рас был скопирован в
characters/srd.py (list_races) и worlds.py (get_world_detail); отбор
разрешённых имён рас/классов дублировался в обоих файлах. Здесь единая
реализация: добавили поле в выдачу — правится в одном месте.
"""

from app.knowledge.srd_rules import (
    RACIAL_TRAITS, RACE_DESCRIPTIONS, FLAVORS, RACIAL_SUBRACES, RACE_STAT_BONUSES,
    CLASS_PROFICIENCIES, CLASS_FLAVORS, CLASS_DESCRIPTIONS, CLASS_FEATURES_L1,
    CLASS_HIT_DIE, CLASS_STARTING_EQUIPMENT,
)
from app.knowledge.worlds import (
    get_world_races, get_world_classes,
    world_exclusive_races, world_exclusive_classes,
    resolve_race_key, resolve_class_key,
)


def visible_race_names(world_key: str | None) -> list[str]:
    """Имена рас, разрешённые в мире (или все, кроме эксклюзивных других миров)."""
    allowed = get_world_races(world_key)
    if allowed is not None:
        return allowed
    excluded = world_exclusive_races()
    return [n for n in RACIAL_TRAITS if n not in excluded]


def visible_class_names(world_key: str | None) -> list[str]:
    """Имена классов, разрешённые в мире (или все, кроме эксклюзивных других миров)."""
    allowed = get_world_classes(world_key)
    if allowed is not None:
        return allowed
    excluded = world_exclusive_classes()
    return [n for n in CLASS_PROFICIENCIES if n not in excluded]


def build_race_entries(race_names: list[str], world_key: str | None, *, brief: bool = False) -> list[dict]:
    """Полные описания рас: черты, бонусы, подрасы.

    brief=True — только названия и описания без trait'ов/подрас (превью списка).
    """
    result = []
    for r in race_names:
        race_key = resolve_race_key(world_key, r)
        has_subraces = r in RACIAL_SUBRACES
        # Для рас с подрасами — первая подраса как база (для preview)
        if has_subraces:
            base_subs = RACIAL_SUBRACES[r]["subraces"]
            stat_bonuses = base_subs[0].get("stat_bonuses", {}) if base_subs else {}
            subraces = [{"key": sr["key"], "name": sr["name"], "desc": sr["desc"],
                         "stat_bonuses": sr.get("stat_bonuses", {})}
                        for sr in base_subs]
        else:
            stat_bonuses = RACE_STAT_BONUSES.get(race_key, {})
            subraces = []
        result.append({
            "name": r,
            "description": RACE_DESCRIPTIONS.get(race_key, ""),
            "flavor": FLAVORS.get(race_key, ""),
            "traits": [] if brief else RACIAL_TRAITS.get(race_key, []),
            "stat_bonuses": stat_bonuses,
            "has_subraces": has_subraces,
            "subraces": subraces if not brief else [],
        })
    return result


def build_class_entries(class_names: list[str], world_key: str | None) -> list[dict]:
    """Полные описания классов: владения, умения 1-го уровня, снаряжение, хит-дайс.

    Имя в выдаче — plain (для UI), данные берутся по ключу с учётом мира
    (resolve_class_key маппит «Воин» → «Воин__ravenloft» и т.п.).
    """
    result = []
    for name in class_names:
        class_key = resolve_class_key(world_key, name)
        result.append({
            "name": name,
            "description": CLASS_FLAVORS.get(class_key, CLASS_DESCRIPTIONS.get(class_key, "")),
            "flavor": CLASS_DESCRIPTIONS.get(class_key, ""),
            "hit_die": CLASS_HIT_DIE.get(class_key, 8),
            "proficiencies": CLASS_PROFICIENCIES.get(class_key, {}),
            "features": CLASS_FEATURES_L1.get(class_key, []),
            "starting_equipment": CLASS_STARTING_EQUIPMENT.get(class_key, {}),
        })
    return result
