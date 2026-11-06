"""Классификация мировых классов для мультикласса и hit-die.

Мировые классы (ключ "<Имя>__<world>", например "Солдат__nuclear_wasteland")
не имеют ручных записей в MULTICLASS_REQUIREMENTS / MULTICLASS_PROFICIENCIES /
CLASS_HIT_DIE. Здесь — АВТОГЕНЕРАЦИЯ по ключевым словам в имени класса:

- характеристика требования мультикласса (порог 13, как в PHB):
  боевые/силовые → str, ловкие/стрелковые → dex, технические → int,
  духовные/медицинские/психические → wis, лидерские/социальные → cha.
- hit_die: танки 10/12, средние боевые 8/10, лёгкие/кастеры/технические 6/8.
- владения при мультиклассе: разумный минимум по типу класса.

Приоритет: точечные переопределения (_OVERRIDES) > ключевая классификация
(_CLASSIFY) > дефолт. Возвращает только {6, 8, 10, 12} для hit_die.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------
# Точечные переопределения (явные смыслы, где классификатор ошибся бы)
# ---------------------------------------------------------------

_OVERRIDES: dict[str, dict] = {
    # Космодесант в d10+ power armor — танк, но не tarrasque: 10
    "Империум: Космодесантник": {"hit_die": 10, "stat": "str"},
    "Хаос: Космодесантник Хаоса": {"hit_die": 10, "stat": "str"},
    # Тяжёлые штурмовые
    "Штурмовик": {"hit_die": 10, "stat": "str"},
    "Штурмовик цитадели": {"hit_die": 10, "stat": "str"},
    "Имперский штурмовик": {"hit_die": 10, "stat": "str"},
    "Империум: Имперский гвардеец": {"hit_die": 8, "stat": "str"},
    "Некроны: Воин-некрон": {"hit_die": 10, "stat": "str"},
    "Некроны: Некрон-лорд": {"hit_die": 12, "stat": "cha"},
    "Орки: Ноб": {"hit_die": 12, "stat": "str"},
    "Орки: Орк-бой": {"hit_die": 10, "stat": "str"},
    "Тау: Боевой костюм": {"hit_die": 10, "stat": "str"},
    "Тау: Огненный воин": {"hit_die": 8, "stat": "str"},
    # Психика/духовность
    "Империум: Псайкер": {"hit_die": 6, "stat": "wis"},
    "Псайкер-оперативник": {"hit_die": 6, "stat": "wis"},
    "Псионик": {"hit_die": 6, "stat": "wis"},
    "Пси-навигатор": {"hit_die": 6, "stat": "wis"},
    "Телепат": {"hit_die": 6, "stat": "wis"},
    "Хаос: Псайкер Хаоса": {"hit_die": 6, "stat": "wis"},
    "Эльдары: Псайкер": {"hit_die": 6, "stat": "wis"},
    "Хаос: Еретик-аколит": {"hit_die": 8, "stat": "wis"},
    "Хаос: Культист": {"hit_die": 6, "stat": "wis"},
    "Хаос: Одержимый": {"hit_die": 8, "stat": "cha"},
    "Империум: Инквизитор": {"hit_die": 8, "stat": "wis"},
    "Империум: Комиссар": {"hit_die": 8, "stat": "cha"},
    "Империум: Ассасин": {"hit_die": 8, "stat": "dex"},
    # Ловкачи
    "Империум: Ассасин "[:0] + "Вор": {"hit_die": 8, "stat": "dex"},
    "Снайпер": {"hit_die": 8, "stat": "dex"},
    "Диверсант": {"hit_die": 8, "stat": "dex"},
    "Налётчик": {"hit_die": 8, "stat": "dex"},
    "Курьер": {"hit_die": 8, "stat": "dex"},
    "Охотник за головами": {"hit_die": 8, "stat": "dex"},
    "Эльдары: Арлекин": {"hit_die": 8, "stat": "dex"},
    "Эльдары: Призрак": {"hit_die": 8, "stat": "dex"},
    "Абордажник": {"hit_die": 10, "stat": "str"},
    # Технические
    "Нетраннер": {"hit_die": 6, "stat": "int"},
    "Хакер": {"hit_die": 6, "stat": "int"},
    "Сетевой взломщик": {"hit_die": 6, "stat": "int"},
    "Технарь": {"hit_die": 8, "stat": "int"},
    "Механик": {"hit_die": 8, "stat": "int"},
    "Оператор боевых дронов": {"hit_die": 8, "stat": "int"},
    "Тау: Командир дронов": {"hit_die": 8, "stat": "int"},
    "Орки: Орк-механик": {"hit_die": 8, "stat": "int"},
    "Некроны: Криптек": {"hit_die": 8, "stat": "int"},
    "Инженер варп-двигателей": {"hit_die": 6, "stat": "int"},
    # Пилоты
    "Пилот": {"hit_die": 8, "stat": "dex"},
    "Космический пилот": {"hit_die": 8, "stat": "dex"},
    "Пилот дирижабля": {"hit_die": 8, "stat": "dex"},
    "Водитель": {"hit_die": 8, "stat": "dex"},
    "Машинист": {"hit_die": 8, "stat": "int"},
    # Социальные
    "Политик": {"hit_die": 8, "stat": "cha"},
    "Дипломат": {"hit_die": 8, "stat": "cha"},
    "Адвокат": {"hit_die": 8, "stat": "cha"},
    "Торговец": {"hit_die": 8, "stat": "cha"},
    "Информатор": {"hit_die": 6, "stat": "cha"},
    "Мошенник": {"hit_die": 8, "stat": "cha"},
    "Риелтор": {"hit_die": 8, "stat": "cha"},
    # Живучие/рабочие
    "Шахтёр": {"hit_die": 10, "stat": "con"},
    "Строитель": {"hit_die": 10, "stat": "con"},
    "Пожарный": {"hit_die": 10, "stat": "con"},
    "Выживальщик": {"hit_die": 10, "stat": "con"},
    "Кочевник": {"hit_die": 10, "stat": "con"},
    "Вышибала": {"hit_die": 12, "stat": "str"},
    "Тяжёлый дроид": {"hit_die": 12, "stat": "str"},
    "Оружейник": {"hit_die": 8, "stat": "int"},
    "Мастер рун": {"hit_die": 8, "stat": "int"},
    "Алхимик": {"hit_die": 6, "stat": "int"},
    "Алхимик-техник": {"hit_die": 6, "stat": "int"},
    "Химик": {"hit_die": 6, "stat": "int"},
    "Учёный": {"hit_die": 6, "stat": "int"},
    "Учёный-ксенолог": {"hit_die": 6, "stat": "int"},
    "Медик": {"hit_die": 8, "stat": "wis"},
    "Полевой медик": {"hit_die": 8, "stat": "wis"},
    "Доктор": {"hit_die": 8, "stat": "wis"},
    "Медик-техник": {"hit_die": 8, "stat": "wis"},
    "Психолог": {"hit_die": 8, "stat": "wis"},
    # Мародёр — грабитель, dex
    "Мародёр": {"hit_die": 8, "stat": "dex"},
    # Уличные
    "Уличный боец": {"hit_die": 8, "stat": "str"},
    "Уличный панк": {"hit_die": 8, "stat": "dex"},
    # Стражи
    "Страж": {"hit_die": 10, "stat": "str"},
    "Страж мёртвой зоны": {"hit_die": 10, "stat": "str"},
    "Некроны: Страж гробницы": {"hit_die": 10, "stat": "str"},
    "Полицейский": {"hit_die": 8, "stat": "str"},
    "Телохранитель": {"hit_die": 10, "stat": "str"},
    # Журналист — наблюдатель
    "Журналист": {"hit_die": 6, "stat": "cha"},
    # Лидеры
    "Лидер": {"hit_die": 8, "stat": "cha"},
    "Лидер анклава": {"hit_die": 8, "stat": "cha"},
    "Лидер сопротивления": {"hit_die": 8, "stat": "cha"},
    "Тау: Аун": {"hit_die": 6, "stat": "cha"},
    # Колдуны/маги миров
    "Маг": {"hit_die": 6, "stat": "int"},
    "Уличный маг": {"hit_die": 6, "stat": "int"},
    "Инженер-маг": {"hit_die": 6, "stat": "int"},
    "Техно-маг": {"hit_die": 6, "stat": "int"},
    "Маго-рыцарь": {"hit_die": 8, "stat": "int"},
    "Рунный стрелок": {"hit_die": 8, "stat": "dex"},
    # Базовые D&D-классы, встречающиеся в мирах без суффикса — не переопределяем
    # (они уже есть в ручных словарях; классификатор их не испортит —
    #  см. get_world_class_rules: сначала проверяются ручные записи).
}

# ---------------------------------------------------------------
# Ключевая классификация (проверяется сверху вниз, первая группа побеждает)
# ---------------------------------------------------------------

# (паттерн, stat, hit_die, profs-тип)
_CLASSIFY: list[tuple[re.Pattern, str, int, str]] = [
    (re.compile(r"Космодесант|Штурмовик|Гвардеец|Громила|Вышибала|Ноб|Тяжёлый|Боевой костюм"),
     "str", 10, "tank"),
    (re.compile(r"Снайпер|Стрелок|Плут|Вор|Разведчик|Диверсант|Налётчик|Курьер|Мародёр|Ассасин|Арлекин|Призрак"),
     "dex", 8, "dexterous"),
    (re.compile(r"Хакер|Нетраннер|Инженер|Технарь|Техник|Механик|Учёный|Химик|Алхимик|Дрон|Криптек|Машинист|Взломщик|Оружейник|Рун"),
     "int", 6, "technical"),
    (re.compile(r"Медик|Доктор|Жрец|Шаман|Псионик|Псайкер|Телепат|Психолог|Аколит|Культист|Инквизитор"),
     "wis", 8, "spiritual"),
    (re.compile(r"Лидер|Дипломат|Политик|Агитатор|Адвокат|Торговец|Комиссар|Аун|Информатор|Мошенник|Риелтор|Журналист|Одержимый"),
     "cha", 8, "social"),
    (re.compile(r"Пилот|Водитель|Водила"),
     "dex", 8, "pilot"),
    (re.compile(r"Солдат|Наёмник|Охотник|Войн|Воин|Боец|Боевик|Рейнджер|Следопыт|Абордажник|Чемп[еи]он"),
     "str", 10, "martial"),
    (re.compile(r"Танк|Страж|Гвардия|Строитель|Шахтёр|Пожарный|Выживальщик|Кочевник|Дроид"),
     "str", 10, "tank"),
    (re.compile(r"Маг|Волшебник|Колдун|Чародей|Некромант"),
     "int", 6, "technical"),
    (re.compile(r"Ассасин"),
     "dex", 8, "dexterous"),
]

# ---------------------------------------------------------------
# Владения по типу класса
# ---------------------------------------------------------------

_PROFS_BY_TYPE: dict[str, dict] = {
    "tank":       {"armor": ["light", "medium", "heavy", "shield"], "weapons": ["simple", "martial"], "tools": [], "skills": 0, "saves": []},
    "martial":    {"armor": ["light", "medium", "shield"], "weapons": ["simple", "martial"], "tools": [], "skills": 1, "saves": []},
    "dexterous":  {"armor": ["light"], "weapons": ["simple", "martial"], "tools": ["thieves_tools"], "skills": 1, "saves": []},
    "technical":  {"armor": ["light"], "weapons": ["simple"], "tools": ["tinker_tools"], "skills": 1, "saves": []},
    "spiritual":  {"armor": ["light", "medium", "shield"], "weapons": ["simple"], "tools": [], "skills": 1, "saves": []},
    "social":     {"armor": [], "weapons": ["simple"], "tools": [], "skills": 1, "saves": []},
    "pilot":      {"armor": ["light"], "weapons": ["simple"], "tools": ["vehicles"], "skills": 1, "saves": []},
}

_DEFAULT_PROFS = {"armor": ["light"], "weapons": ["simple"], "tools": [], "skills": 1, "saves": []}


def _normalize_class_name(class_key: str) -> str:
    """"<Имя>__<world>" → "<Имя>"; plain имя — как есть."""
    return class_key.split("__", 1)[0] if "__" in class_key else class_key


def get_world_class_rules(class_key: str) -> dict:
    """Правила мультикласса/хитов для мирового класса.

    class_key: "<Имя>__<world>" или plain "<Имя>" (идёт через overrides).
    Возвращает:
      {
        "requirement": {"stat": "str", "value": 13} | {"stat": "str", "value": 13, "stat2": "wis"} (группы OR не нужны — по одному стату),
        "proficiencies": {"armor": [...], "weapons": [...], "tools": [...], "skills": int, "saves": []},
        "hit_die": 6|8|10|12,
        "source": "override" | "keyword" | "default",
      }
    """
    name = _normalize_class_name(class_key)

    if name in _OVERRIDES:
        ov = _OVERRIDES[name]
        return {
            "requirement": {ov["stat"]: 13},
            "proficiencies": dict(_PROFS_BY_TYPE.get(_classify_type(name), _DEFAULT_PROFS)),
            "hit_die": ov["hit_die"],
            "source": "override",
        }

    for pattern, stat, hit_die, prof_type in _CLASSIFY:
        if pattern.search(name):
            return {
                "requirement": {stat: 13},
                "proficiencies": dict(_PROFS_BY_TYPE[prof_type]),
                "hit_die": hit_die,
                "source": "keyword",
            }

    return {
        "requirement": {"str": 13},
        "proficiencies": dict(_DEFAULT_PROFS),
        "hit_die": 8,
        "source": "default",
    }


def _classify_type(name: str) -> str:
    """Тип класса по ключевым словам (для profs override-классов)."""
    for pattern, _stat, _die, prof_type in _CLASSIFY:
        if pattern.search(name):
            return prof_type
    return "martial"
