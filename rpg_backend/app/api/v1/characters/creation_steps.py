"""Чистые шаги POST /characters/create.

Разбито из create_character (раунд 8, снижение цикломатической сложности).
Каждая функция — один шаг создания персонажа, детерминированная, без БД.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.knowledge.srd_rules import (
    BACKGROUNDS,
    CLASS_FEATURES_L1,
    CLASS_PROFICIENCIES,
    RACE_STAT_BONUSES,
    RACIAL_SUBRACES,
    RACIAL_TRAITS,
    SUBCLASS_OPTIONS,
)
from app.knowledge.worlds import (
    WORLD_TEMPLATES,
    get_world_classes,
    get_world_races,
    resolve_class_key,
    resolve_race_key,
    WORLD_RACE_ALIASES,
    WORLD_CLASS_ALIASES,
)


def _canonical(name: str, valid: list[str]) -> str | None:
    """Case-insensitive сопоставление с каноническими ключами словарей."""
    if name in valid:
        return name
    folded = name.casefold()
    for v in valid:
        if v.casefold() == folded:
            return v
    return None


def resolve_world(world: str | None) -> str:
    """Шаг 0: мир — определяем до валидации расы/класса."""
    world_key = world or "forgotten_realms"
    if world_key not in WORLD_TEMPLATES:
        raise HTTPException(400, detail=f"Неизвестный мир: {world}. Доступны: {', '.join(WORLD_TEMPLATES.keys())}")
    return world_key


def _canonize_world_entity(
    world_key: str, raw: str, *, valid_keys: list[str], aliases: dict,
    resolver, error_label: str, allowed: str,
) -> str:
    """Общая канонизация расы/класса для выбранного мира.

    Порядок: точное попадание в алиасы мира (case-insensitive — имена вида
    «Проклятый» существуют только под суффиксом и не найдутся среди plain-ключей)
    → точное попадание в валидные ключи → _canonical (case-insensitive) →
    resolver (маппит чистые имена на ключи с суффиксами) → валидация.
    """
    folded = raw.casefold()
    for ui_name, target in aliases.items():
        if ui_name.casefold() == folded and target in valid_keys:
            return target
    name = raw if raw in valid_keys else (_canonical(raw, valid_keys) or raw)
    key = resolver(world_key, name)
    if key not in valid_keys:
        raise HTTPException(400, detail=f"{error_label}: {raw}. Доступны: {allowed}")
    return key


def canonize_race(world_key: str, raw: str) -> str:
    """Канонизация расы: resolve_race_key маппит чистые имена на ключи с суффиксами.
    title() убран: он ломает имена с дефисом («человек-чистый» → «Человек-Чистый»);
    регистр нормализует _canonical (case-insensitive), мир — resolve_race_key."""
    valid_races = list(RACIAL_TRAITS.keys())
    return _canonize_world_entity(
        world_key, raw,
        valid_keys=valid_races,
        aliases=WORLD_RACE_ALIASES.get(world_key, {}),
        resolver=resolve_race_key,
        error_label="Неизвестная раса",
        allowed=', '.join(sorted(set(v.split('__')[0] for v in valid_races))),
    )


def canonize_class(world_key: str, raw: str) -> str:
    """Канонизация класса с учётом мира. Без title(): дефисы («Следопыт-пустошей»)
    и регистр обрабатываются через _canonical + resolve_class_key."""
    valid_classes = list(CLASS_PROFICIENCIES.keys())
    return _canonize_world_entity(
        world_key, raw,
        valid_keys=valid_classes,
        aliases=WORLD_CLASS_ALIASES.get(world_key, {}),
        resolver=resolve_class_key,
        error_label="Неизвестный класс",
        allowed=', '.join(sorted(valid_classes)),
    )


def check_world_availability(world_key: str, race_key: str, class_key: str, raw_race: str, raw_class: str) -> None:
    """Проверка доступности расы/класса в выбранном мире."""
    world_name = WORLD_TEMPLATES[world_key].name

    allowed_races = get_world_races(world_key)
    if allowed_races is not None:
        allowed_keys = {resolve_race_key(world_key, r) for r in allowed_races}
        if race_key not in allowed_keys:
            raise HTTPException(
                400,
                detail=f"Раса «{raw_race}» не доступна в мире «{world_name}». Доступны: {', '.join(allowed_races)}",
            )

    allowed_classes = get_world_classes(world_key)
    if allowed_classes is not None:
        allowed_keys = {resolve_class_key(world_key, c) for c in allowed_classes}
        if class_key not in allowed_keys:
            raise HTTPException(
                400,
                detail=f"Класс «{raw_class}» не доступен в мире «{world_name}». Доступны: {', '.join(allowed_classes)}",
            )


def _append_subrace_traits(racial: list[dict], sr: dict) -> None:
    """Добавить черты подрасы (имя, desc, flavor + доп. черты)."""
    racial.append({"name": f"Подраса: {sr['name']}", "desc": sr["desc"], "flavor": sr["flavor"]})
    for et in sr.get("extra_traits", []):
        racial.append(et)


def collect_racial_traits(data, race_key: str | None = None) -> tuple[list[dict], str, dict | None]:
    """Собрать расовые черты: раса + подраса + смешанное наследие.

    race_key — канонизированный ключ расы (результат canonize_race, с суффиксом мира
    для world-рас). Если не передан — используется data.race как есть.
    Returns (racial, subrace_name, subrace_data). mixed_heritage берётся из data.
    """
    race_name = race_key if race_key else data.race
    mixed_data = data.mixed_heritage
    racial = list(RACIAL_TRAITS.get(race_name, []))  # копия, чтобы не мутировать оригинал

    # Подраса — добавляем специфичные черты
    subrace_name = ""
    subrace_data = None
    if data.subrace and race_name in RACIAL_SUBRACES:
        for sr in RACIAL_SUBRACES[race_name]["subraces"]:
            if sr["key"] == data.subrace:
                subrace_data = sr
                subrace_name = sr["name"]
                _append_subrace_traits(racial, sr)
                break

    # Смешанная раса — черты из mixed_heritage
    if race_name == "Смешанная" and mixed_data:
        for t in mixed_data.get("physical_traits", []):
            racial.append({"name": t["name"], "desc": t["desc"], "flavor": f"От {t['source']}"})
        for t in mixed_data.get("magical_traits", []):
            racial.append({"name": t["name"], "desc": t["desc"], "flavor": f"От {t['source']}"})
        for t in mixed_data.get("visual_traits", []):
            racial.append({"name": t["name"], "desc": t["desc"], "flavor": f"Внешность: {t['source']}"})
        # Наследие подрас — черты и стат-бонусы
        for sr in mixed_data.get("inherited_subraces", []):
            racial.append({
                "name": f"Наследие подрасы: {sr['name']} ({sr['race']})",
                "desc": sr["desc"],
                "flavor": sr["flavor"],
            })
            for et in sr.get("extra_traits", []):
                racial.append(et)

    return racial, subrace_name, subrace_data


def match_subclass(class_name: str, subclass_key: str | None) -> tuple[list, list, dict | None]:
    """Найти подкласс: returns (class_feats, subclass_features, subclass_data)."""
    class_feats = list(CLASS_FEATURES_L1.get(class_name, []))
    subclass_options = SUBCLASS_OPTIONS.get(class_name)
    subclass_features: list = []
    subclass_data = None
    if subclass_options and subclass_key:
        for opt in subclass_options["options"]:
            if opt["key"] == subclass_key:
                subclass_data = opt
                subclass_features = opt["features"]
                class_feats = class_feats + [
                    {"name": f"{subclass_options['label']}: {opt['name']}",
                     "desc": opt["desc"],
                     "flavor": subclass_options.get("flavor", "")}
                ] + opt["features"]
                break
    return class_feats, subclass_features, subclass_data


def apply_stat_bonuses(data, race_key: str, subrace_data: dict | None) -> dict:
    """Статы: стандартный набор + расовые/подрасовые/наследственные бонусы."""
    # Стандартный набор D&D 2024 (10-11 по всем характеристикам)
    standard_stats = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    actual_stats = dict(data.stats) if data.stats else dict(standard_stats)

    race_bonuses = RACE_STAT_BONUSES.get(race_key, {})
    for stat, bonus in race_bonuses.items():
        actual_stats[stat] = actual_stats.get(stat, 10) + bonus

    if subrace_data and subrace_data.get("stat_bonuses"):
        for stat, bonus in subrace_data["stat_bonuses"].items():
            actual_stats[stat] = actual_stats.get(stat, 10) + bonus

    if data.race == "Смешанная" and data.mixed_heritage:
        for sr in data.mixed_heritage.get("inherited_subraces", []):
            for stat, bonus in sr.get("stat_bonuses", {}).items():
                actual_stats[stat] = actual_stats.get(stat, 10) + bonus

    return actual_stats


def build_backgrounds() -> list[dict]:
    """Предыстории для выбора."""
    return [
        {"name": name, "feature": bg["feat"], "feature_desc": "", "flavor": ""}
        for name, bg in BACKGROUNDS.items()
    ]
