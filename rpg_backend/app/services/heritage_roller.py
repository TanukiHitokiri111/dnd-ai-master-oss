"""
Модуль броска смешанного наследия (Mixed Heritage Roller).
D&D 2014 PHB: кастомная смесь рас для персонажей смешанного происхождения.

Логика:
- На входе: {раса → процент родословной} (например {"Эльф": 50, "Человек": 50})
- Определяется доминантная (наибольший %)
- Для каждой расы бросаются физические и магические черты
  - Шанс = базовая вероятность черты × (процент/50)
- Бросаются визуальные черты доминантной расы
- Скорость взвешивается по процентам
- Языки: Общий всегда + расовые с долей ≥ порога
"""

import random
import json
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

from app.knowledge.srd_rules import (
    COMPAT_RULES,
    MIXED_HERITAGE_CONFIG,
    MIXED_VISUAL_TRAITS,
    MIXED_TRAIT_CATEGORIES,
    MIXED_LANGUAGE_THRESHOLD,
    RACIAL_SUBRACES,
)
try:
    from app.knowledge.trait_mechanics import TRAIT_MECHANICS
except ImportError:
    TRAIT_MECHANICS = {}  # fallback: тестовая среда без модуля


def get_compatible_races(race_name: str) -> list[str]:
    """Возвращает список рас, с которыми можно смешивать данную."""
    rule = COMPAT_RULES.get(race_name)
    if not rule or not rule.get("can_mix", False):
        return []
    return rule.get("compatible_with", [])


def _universal_races() -> set[str]:
    """Расы группы UNIVERSAL (совместимы со всеми кроме CONSTRUCT/UNDEAD)."""
    return {r for r, rule in COMPAT_RULES.items() if rule.get("group") == "UNIVERSAL"}


def _check_universal_pair(race: str, other: str, errors: list[str]) -> None:
    """UNIVERSAL × обычная: запрет только на CONSTRUCT/UNDEAD_ADJACENT."""
    other_group = COMPAT_RULES.get(other, {}).get("group", "")
    if other_group in ("CONSTRUCT", "UNDEAD_ADJACENT"):
        errors.append(
            f"Универсальная раса «{race}» несовместима с «{other}» ({other_group})"
        )


def _check_normal_pair(race: str, rule: dict, other: str, universal_races: set[str], errors: list[str]) -> None:
    """Обычная × обычная: other должен быть в compatible_with расы."""
    if other in universal_races:
        return  # universal races can mix with anyone
    if other not in rule.get("compatible_with", []):
        other_rule = COMPAT_RULES.get(other, {})
        errors.append(
            f"Раса «{race}» ({rule.get('group', '?')}) несовместима с «{other}» "
            f"({other_rule.get('group', '?')})"
        )


def check_compatibility(races: list[str]) -> list[str]:
    """Проверяет совместимость списка рас для смешанного наследия.

    Returns:
        Список ошибок (пустой если всё ок).
    """
    errors = []
    universal_races = _universal_races()
    for race in races:
        if race not in COMPAT_RULES:
            errors.append(f"Раса «{race}» не найдена в COMPAT_RULES")
            continue
        rule = COMPAT_RULES[race]
        if not rule.get("can_mix", False):
            errors.append(f"Раса «{race}» ({rule.get('group', '?')}) не может скрещиваться ни с кем")
            continue
        # UNIVERSAL races (Чейнджлинг, Дампир) совместимы со всеми КРОМЕ CONSTRUCT/UNDEAD
        if race in universal_races:
            for other in races:
                if other != race:
                    _check_universal_pair(race, other, errors)
            continue
        for other in races:
            if other == race:
                continue
            _check_normal_pair(race, rule, other, universal_races, errors)
    return errors


def _scale_chance(base_chance: int, species_pct: int, floor: float = 3.0) -> float:
    """Масштабирует базовый шанс черты пропорционально доле родословной.

    При 50% шанс = базовый, при 100% = ×2, при 25% = ×0.5.
    floor: минимальный шанс (3% для физических, 2% для магических).
    Результат клампится к 100.
    """
    if base_chance <= 0:
        return 0.0
    multiplier = species_pct / 50.0
    return min(100.0, max(floor, base_chance * multiplier))


# --- Категории ключей механик (модульный уровень, см. _apply_mechanics) ---
_SCALAR_KEYS = frozenset({"hp_bonus", "breath_hold", "initiative_bonus"})
_FLAG_KEYS = frozenset({"damage_bonus_pb", "reaction_save", "relentless", "temp_hp"})
_LIST_KEYS = frozenset({"resistances", "damage_immunity", "condition_immunity",
                        "skills", "skill_choices", "cantrips",
                        "save_advantage", "bonus_action", "natural_weapons"})
_DICT_KEYS = frozenset({"speeds"})


def _merge_list_key(result: dict, key: str, items: list) -> None:
    """Union списочных значений без дублей."""
    bucket = result.setdefault(key, [])
    for item in items:
        if item not in bucket:
            bucket.append(item)


def _merge_dict_key(result: dict, key: str, values: dict) -> None:
    """Union словарных значений (speeds): берём максимум по каждому подтюку."""
    if not isinstance(result.get(key), dict) or not result[key]:
        result[key] = {}
    for subkey, subval in values.items():
        cur = result[key].get(subkey)
        result[key][subkey] = subval if cur is None else max(cur, subval)


def _merge_scalar_key(result: dict, key: str, value) -> None:
    """Числовые ключи суммируются, строковые ('pb') — first-wins."""
    if isinstance(value, (int, float)):
        cur = result[key] if key in result and isinstance(result[key], (int, float)) else 0
        result[key] = cur + value
    elif key not in result or not result[key]:
        result[key] = value


def _merge_spells(result: dict, spells: list[dict]) -> None:
    """Union заклинаний по имени."""
    known_names = {s["name"] for s in result.setdefault("spells", [])}
    for sp in spells:
        if sp["name"] not in known_names:
            result["spells"].append(sp)


def _ac_base_number(ac_val) -> int:
    """Базовое число формулы AC: '13' / '13 + dex' → 13; при ошибке парсинга — 10."""
    try:
        return int(ac_val.split("+")[0].strip()) if isinstance(ac_val, str) else int(ac_val)
    except (ValueError, TypeError):
        return 10


def _apply_trait_mechanics(result: dict, acc: dict, mech: dict) -> None:
    """Влить механики одной черты в накопители.

    result: общий словарь (defaultdict-подобный аккумулятор объединений);
    acc: {'darkvision_max': int, 'ac_formulas': [(base, formula)], 'ac_bonus_flat': int}.
    """
    # --- AC (специальная обработка) ---
    if "ac" in mech:
        acc["ac_formulas"].append((_ac_base_number(mech["ac"]), mech["ac"]))

    # --- AC bonus ---
    if "ac_bonus" in mech:
        acc["ac_bonus_flat"] += mech["ac_bonus"]

    # --- Darkvision: max ---
    if "darkvision" in mech:
        acc["darkvision_max"] = max(acc["darkvision_max"], mech["darkvision"])

    # --- List keys: union ---
    for key in _LIST_KEYS:
        if key in mech and isinstance(mech[key], list):
            _merge_list_key(result, key, mech[key])

    # --- Dict keys (speeds): union с max ---
    for key in _DICT_KEYS:
        if key in mech:
            _merge_dict_key(result, key, mech[key])

    # --- Scalar keys: sum / first-wins ---
    for key in _SCALAR_KEYS:
        if key in mech:
            _merge_scalar_key(result, key, mech[key])

    # --- Flag keys: any True → True ---
    for key in _FLAG_KEYS:
        if mech.get(key):
            result[key] = True

    # --- Spells: union by name ---
    if "spells" in mech:
        _merge_spells(result, mech["spells"])


def _cleanup_mechanics_result(result: dict, acc: dict) -> dict:
    """Финализация: выбрать лучшую формулу AC, максимум darkvision,
    убрать пустые ключи и превратить defaultdict в обычный dict."""
    # --- Finalise AC ---
    if acc["ac_formulas"]:
        best_formula = max(acc["ac_formulas"])[1]
        result["ac"] = best_formula
    if acc["ac_bonus_flat"]:
        result["ac_bonus"] = acc["ac_bonus_flat"]

    # --- Darkvision ---
    if acc["darkvision_max"] > 0:
        result["darkvision"] = acc["darkvision_max"]

    # --- Cleanup: empty lists → omit ---
    for key in list(_LIST_KEYS) + ["spells"]:
        if key in result and not result[key]:
            del result[key]

    # --- Numeric keys: нулевые значения не показываем ---
    for key in ("hp_bonus", "ac_bonus", "breath_hold", "initiative_bonus"):
        if key in result and not result[key]:
            del result[key]

    return dict(result)


def _apply_mechanics(traits: list[dict]) -> dict:
    """Извлекает механики из выпавших черт (после дедупликации).

    Собирает все механические эффекты из TRAIT_MECHANICS для отобранных черт.
    Правила объединения:
    - AC: берётся формула с наибольшим базовым числом (если 13 > 12+dex → 13)
    - Resistance/Immunity/Skills/Speed/SaveAdv: объединяются (union)
    - Darkvision: берётся максимальная дальность
    - Всё остальное: суммируется/объединяется
    """
    from collections import defaultdict

    result: dict = defaultdict(list)
    acc = {"darkvision_max": 0, "ac_formulas": [], "ac_bonus_flat": 0}

    for trait in traits:
        source = trait.get("source", "?")
        trait_name = trait["name"]
        mech = TRAIT_MECHANICS.get(source, {}).get(trait_name)
        if not mech:
            continue
        _apply_trait_mechanics(result, acc, mech)

    return _cleanup_mechanics_result(result, acc)


def _validate_species_input(species_percentages: dict[str, int]) -> dict[str, int]:
    """Валидация входных процентов: сумма ~100, все проценты положительны,
    расы известны и могут скрещиваться. Возвращает отфильтрованный словарь."""
    total = sum(species_percentages.values())
    if total <= 0:
        raise ValueError("Сумма процентов должна быть положительной")
    if total < 95 or total > 105:
        raise ValueError(f"Сумма процентов должна быть ~100% (±5), получено: {total}%")

    known: dict[str, int] = {}
    unknown: list[str] = []
    blocked: list[str] = []
    for sp, pct in species_percentages.items():
        if not isinstance(pct, (int, float)) or pct <= 0:
            raise ValueError(f"Процент для расы «{sp}» должен быть положительным числом, получено: {pct}")
        if sp not in MIXED_HERITAGE_CONFIG:
            unknown.append(sp)
            continue
        rule = COMPAT_RULES.get(sp, {})
        if not rule.get("can_mix", False):
            blocked.append(f"{sp} ({rule.get('group', '?')})")
            continue
        known[sp] = pct  # без клампа — пропорции важнее

    if blocked:
        raise ValueError(f"Эти расы не могут скрещиваться: {', '.join(blocked)}")

    if unknown:
        raise ValueError(
            f"Неизвестные расы в MIXED_HERITAGE_CONFIG: {', '.join(unknown)}. "
            f"Доступны: {', '.join(sorted(MIXED_HERITAGE_CONFIG.keys()))}"
        )

    if not known:
        raise ValueError("Нет известных рас в species_percentages")
    return known


def _normalize_to_100(species_percentages: dict[str, int], known: dict[str, int]) -> dict[str, int]:
    """Нормализация процентов до 100 методом largest remainder + отбрасывание нулевых."""
    total_known = sum(known.values())
    if total_known <= 0:
        return known
    # First pass: floor
    floor_sum = 0
    remainders = []
    for sp in known:
        exact = known[sp] / total_known * 100
        floored = int(exact)
        known[sp] = floored
        floor_sum += floored
        remainders.append((exact - floored, sp))
    # Distribute remaining units by largest remainder (cycle if fewer races than units)
    remainders.sort(reverse=True)
    for i in range(100 - floor_sum):
        known[remainders[i % len(remainders)][1]] += 1

    # Фильтруем расы с нулевым процентом (largest_remainder может дать 0)
    dropped = [sp for sp, pct in known.items() if pct == 0]
    if dropped:
        logger.warning("Расы с 0%% после нормализации отброшены: %s (входные: %s)",
                       dropped, list(species_percentages.keys()))
    result = {sp: pct for sp, pct in known.items() if pct > 0}
    if not result:
        raise ValueError("После нормализации все расы получили 0% — проверьте входные данные")
    return result


def roll_physical_and_magical_traits(rng, known: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """Броски физических и магических черт по каждой расе (сортировка по имени
    гарантирует детерминизм при заданном seed)."""
    physical_traits: list[dict] = []
    magical_traits: list[dict] = []
    for species in sorted(known.keys()):
        pct = known[species]
        cfg = MIXED_HERITAGE_CONFIG[species]

        # Физические черты
        for name, trait in cfg.get("physical_traits", {}).items():
            chance = _scale_chance(trait["chance"], pct, floor=3.0)
            if rng.random() * 100 < chance:
                physical_traits.append({
                    "name": name,
                    "desc": trait["desc"],
                    "source": species,
                    "hp_bonus": trait.get("hp_bonus", 0),
                })

        # Магические черты
        for name, trait in cfg.get("magical_traits", {}).items():
            chance = _scale_chance(trait["chance"], pct, floor=2.0)
            if rng.random() * 100 < chance:
                magical_traits.append({
                    "name": name,
                    "desc": trait["desc"],
                    "source": species,
                })
    return physical_traits, magical_traits


def _trait_effect_key(t: dict) -> str:
    """Канонический ключ дедупликации черт по механике из TRAIT_MECHANICS.

    Разные расы могут давать один и тот же эффект с чуть разным названием
    (например «Тёмное зрение 60 футов» vs «Тёмное зрение: 60 футов»).
    """
    mech = TRAIT_MECHANICS.get(t.get("source", ""), {}).get(t["name"])
    if not mech:
        return t["name"]  # fallback: дедупликация по имени
    # Игнорируем аддитивные поля (hp_bonus суммируется отдельно)
    ignore = {"hp_bonus", "ac_bonus", "breath_hold", "initiative_bonus", "bonus_action"}
    parts = []
    for k in sorted(mech):
        if k in ignore:
            continue
        v = mech[k]
        if isinstance(v, (int, float, str, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, dict):
            parts.append(f"{k}={sorted(v.items())}")
        elif isinstance(v, list):
            # Stable serialization for nested dicts (spells, natural_weapons)
            parts.append(f"{k}={sorted(json.dumps(x, sort_keys=True, ensure_ascii=False) if isinstance(x, dict) else str(x) for x in v)}")
    return ";".join(parts) if parts else t["name"]


def _dedup_by_effect_key(traits: list[dict]) -> list[dict]:
    """Дедупликация черт по каноническому ключу механики (не по названию)."""
    seen: set[str] = set()
    out = []
    for t in traits:
        k = _trait_effect_key(t)
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def collect_mechanics_and_hp(physical_traits: list[dict],
                             magical_traits: list[dict]) -> tuple[dict, int]:
    """Механики + hp_bonus: дедупликация черт, _apply_mechanics, затем
    досчёт hp_bonus и darkvision по ВСЕМ сырым чертам (до дедупликации)."""
    physical_traits.sort(key=lambda t: (t["source"],), reverse=True)
    magical_traits.sort(key=lambda t: (t["source"],), reverse=True)
    all_raw = physical_traits + magical_traits

    physical_traits = _dedup_by_effect_key(physical_traits)
    magical_traits = _dedup_by_effect_key(magical_traits)

    # --- Механики из дедуплицированных черт ---
    mechanics = _apply_mechanics(physical_traits + magical_traits)
    hp_bonus = mechanics.pop("hp_bonus", 0)

    # Also sum hp_bonus from ALL raw traits (before dedup, like darkvision)
    seen_hp = set()
    for t in all_raw:
        src = t.get("source", "")
        name = t["name"]
        mech = TRAIT_MECHANICS.get(src, {}).get(name, {})
        if not mech or "hp_bonus" not in mech:
            key = (src, name)
            if key not in seen_hp:
                seen_hp.add(key)
                hp_bonus += t.get("hp_bonus", 0)

    # --- Darkvision: учитываем все источники до дедупликации ---
    for t in all_raw:
        src = t.get("source", "?")
        name = t["name"]
        mech = TRAIT_MECHANICS.get(src, {}).get(name, {})
        if "darkvision" in mech:
            cur = mechanics.get("darkvision", 0)
            mechanics["darkvision"] = max(cur, mech["darkvision"])

    return mechanics, hp_bonus


def _weighted_speed(speeds: list[tuple[int, int]]) -> int:
    """Взвешенная по процентам скорость, округлённая кратно 5, кламп 20..50."""
    total_pct = sum(p for _, p in speeds)
    weighted = sum(s * p for s, p in speeds) / total_pct
    speed = round(weighted / 5) * 5  # кратно 5
    return max(20, min(50, speed))  # allow up to 50 for fast races


def _resolve_size_category(size_categories: list[str]) -> str:
    """Размер потомка: most restrictive, но small+medium → medium."""
    if "tiny" in size_categories:
        # Tiny + medium → small; tiny + small → small
        if "medium" in size_categories or "large" in size_categories:
            return "small"
        return "tiny"
    if "small" in size_categories:
        # small + medium/large → medium (PHB логика)
        if any(sc in ("medium", "large") for sc in size_categories):
            return "medium"
        return "small"
    if "large" in size_categories and "medium" in size_categories:
        return "medium"  # medium dominates in mixed
    if all(sc == "large" for sc in size_categories):
        return "large"  # both parents large → large offspring
    if "large" in size_categories:
        return "medium"  # single large parent → medium offspring
    return "medium"


def roll_visual_traits(rng, dominant: str, known: dict[str, int]) -> list[dict]:
    """Визуальные черты доминантной расы + остальных рас с долей ≥ 30%, с дедупликацией."""
    visual_species = [dominant]
    # Добавляем по убыванию процента остальные расы с порогом ≥ 30%
    for sp in sorted(known, key=lambda s: (known[s], s), reverse=True):
        if sp != dominant and known[sp] >= 30:
            visual_species.append(sp)

    visual_traits: list[dict] = []
    for sp in visual_species:
        for vt in MIXED_VISUAL_TRAITS.get(sp, []):
            # multiplier=0 — черта отключена
            multiplier = vt.get("chance_multiplier", 1.0)
            if multiplier <= 0:
                continue
            base = MIXED_TRAIT_CATEGORIES["visual"]["default_chance"]
            chance = _scale_chance(base * multiplier, known[sp])
            if rng.random() * 100 < chance:
                visual_traits.append({
                    "name": vt["name"],
                    "desc": vt["desc"],
                    "source": sp,
                })

    # Дедупликация визуальных черт
    seen: set[str] = set()
    return [t for t in visual_traits if not (t["name"] in seen or seen.add(t["name"]))]


def resolve_languages(known: dict[str, int]) -> list[str]:
    """Общий всегда + расовые языки с долей родословной ≥ порога."""
    languages = ["Общий"]
    for species, pct in known.items():
        if pct >= MIXED_LANGUAGE_THRESHOLD:
            for lang in MIXED_HERITAGE_CONFIG[species].get("languages", []):
                if lang not in languages:
                    languages.append(lang)
    return languages


def roll_inherited_subraces(rng, known: dict[str, int]) -> list[dict]:
    """Наследие подрас: шанс проявления = процент родословной
    (30% эльф = 30% шанс наследовать подрасу)."""
    inherited_subraces: list[dict] = []
    for species, pct in known.items():
        if species not in RACIAL_SUBRACES:
            continue
        if rng.random() * 100 < pct:
            subraces = RACIAL_SUBRACES[species]["subraces"]
            chosen = rng.choice(subraces)
            inherited_subraces.append({
                "race": species,
                "key": chosen.get("key", ""),
                "name": chosen.get("name", "???"),
                "desc": chosen.get("desc", ""),
                "flavor": chosen.get("flavor", ""),
                "stat_bonuses": chosen.get("stat_bonuses", {}),
                "extra_traits": chosen.get("extra_traits", []),
            })
    return inherited_subraces


def roll_mixed_heritage(
    species_percentages: dict[str, int],
    seed: Optional[int] = None,
) -> dict:
    """Бросает смешанное наследие для персонажа.

    Args:
        species_percentages: {"Раса": процент} — сумма должна быть ~100.
        seed: опциональное зерно для воспроизводимости.

    Returns:
        {
            "dominant_species": str,
            "species_percentages": dict,
            "physical_traits": [{"name": str, "desc": str, "source": str}, ...],
            "magical_traits":  [{"name": str, "desc": str, "source": str}, ...],
            "visual_traits":   [{"name": str, "desc": str, "source": str}, ...],
            "speed": int,
            "size_category": str,
            "languages": [str, ...],
            "hp_bonus": int,
        }
    """
    rng = random.Random(seed)  # random.Random(None) seeds from system entropy

    # --- Валидация + нормализация + совместимость ---
    known = _validate_species_input(species_percentages)
    known = _normalize_to_100(species_percentages, known)
    compat_errors = check_compatibility(list(known.keys()))
    if compat_errors:
        raise ValueError("Несовместимые расы: " + "; ".join(compat_errors))

    # --- Доминантная раса (по наибольшему проценту) ---
    dominant = max(known, key=lambda s: (known[s], s))

    # --- Броски черт + сбор скоростей (сортируем расы для детерминизма) ---
    physical_traits, magical_traits = roll_physical_and_magical_traits(rng, known)
    speeds = [(MIXED_HERITAGE_CONFIG[sp].get("speed", 30), known[sp]) for sp in sorted(known)]

    # --- Механики + hp_bonus (внутри: сортировка по source %, дедупликация) ---
    mechanics, hp_bonus = collect_mechanics_and_hp(physical_traits, magical_traits)

    speed = _weighted_speed(speeds)
    size_category = _resolve_size_category([MIXED_HERITAGE_CONFIG[s].get("size_category", "medium") for s in known])

    # --- Визуальные черты, языки, подрасы ---
    visual_traits = roll_visual_traits(rng, dominant, known)
    languages = resolve_languages(known)
    inherited_subraces = roll_inherited_subraces(rng, known)

    return {
        "dominant_species": dominant,
        "species_percentages": known,
        "physical_traits": physical_traits,
        "magical_traits": magical_traits,
        "visual_traits": visual_traits,
        "speed": speed,
        "size_category": size_category,
        "languages": languages,
        "hp_bonus": hp_bonus,
        "inherited_subraces": inherited_subraces,
        "mechanics": mechanics,
    }
