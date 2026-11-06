"""
Система рандомной генерации предметов для D&D AI Master.

Содержит:
1. Модификаторы предметов (статы +/-, описания, редкость)
2. Лут-таблицы по биомам
3. Функции генерации предметов с учётом класса и предыстории
"""

import random
import re
from typing import Optional

# ============================================================
# ПРЕФИКСЫ И СУФФИКСЫ (модификаторы качества)
# ============================================================

ITEM_PREFIXES = {
    "common": {
        "rusty": {"damage_bonus": -1, "value_mult": 0.5, "name_prefix": "Ржавый"},
        "worn": {"ac_penalty": -1, "value_mult": 0.6, "name_prefix": "Потрёпанный"},
        "crude": {"damage_bonus": -1, "ac_penalty": -1, "value_mult": 0.3, "name_prefix": "Грубый"},
        "old": {"value_mult": 0.7, "name_prefix": "Старый"},
        "brittle": {"damage_bonus": -1, "break_chance": 0.15, "value_mult": 0.4, "name_prefix": "Хрупкий"},
        "dull": {"damage_bonus": -1, "value_mult": 0.6, "name_prefix": "Тупой"},
        "chipped": {"damage_bonus": -1, "value_mult": 0.5, "name_prefix": "Щербатый"},
        "stained": {"value_mult": 0.7, "name_prefix": "В пятнах"},
    },
    "uncommon": {
        "fine": {"damage_bonus": 1, "value_mult": 1.5, "name_prefix": "Добротный"},
        "sharp": {"damage_bonus": 1, "value_mult": 1.3, "name_prefix": "Острый"},
        "reinforced": {"ac_bonus": 1, "value_mult": 1.8, "name_prefix": "Укреплённый"},
        "engraved": {"value_mult": 2.0, "name_prefix": "Гравированный"},
        "balanced": {"damage_bonus": 1, "value_mult": 1.5, "name_prefix": "Сбалансированный"},
        "polished": {"value_mult": 1.4, "name_prefix": "Полированный"},
        "ornate": {"cha_bonus": 1, "value_mult": 2.5, "name_prefix": "Украшенный"},
        "lightweight": {"dex_bonus": 1, "value_mult": 1.8, "name_prefix": "Облегчённый"},
    },
    "rare": {
        "flawless": {"damage_bonus": 2, "value_mult": 4.0, "name_prefix": "Безупречный"},
        "masterwork": {"damage_bonus": 2, "value_mult": 5.0, "name_prefix": "Шедевральный"},
        "enchanted": {"damage_bonus": 1, "magic_bonus": 1, "value_mult": 6.0, "name_prefix": "Зачарованный"},
        "ancient": {"magic_bonus": 1, "wis_bonus": 1, "value_mult": 5.0, "name_prefix": "Древний"},
        "dragonforged": {"damage_bonus": 2, "str_bonus": 1, "value_mult": 7.0, "name_prefix": "Драконьей ковки"},
        "shadowforged": {"damage_bonus": 1, "dex_bonus": 2, "value_mult": 6.0, "name_prefix": "Теневой"},
        "runed": {"magic_bonus": 2, "value_mult": 5.0, "name_prefix": "Рунический"},
        "celestial": {"damage_bonus": 1, "wis_bonus": 2, "value_mult": 8.0, "name_prefix": "Небесный"},
    },
    "epic": {
        "legendary": {"damage_bonus": 3, "magic_bonus": 2, "value_mult": 15.0, "name_prefix": "Легендарный"},
        "mythic": {"damage_bonus": 3, "str_bonus": 2, "dex_bonus": 2, "value_mult": 20.0, "name_prefix": "Мифический"},
        "divine": {"damage_bonus": 2, "magic_bonus": 3, "wis_bonus": 2, "value_mult": 25.0, "name_prefix": "Божественный"},
        "demonic": {"damage_bonus": 4, "magic_bonus": 1, "cha_penalty": -2, "value_mult": 18.0, "name_prefix": "Демонический"},
        "void": {"magic_bonus": 4, "con_penalty": -2, "value_mult": 20.0, "name_prefix": "Бездны"},
    },
}

ITEM_SUFFIXES = {
    "common": {
        "of_rust": {"damage_bonus": -1, "name_suffix": "ржавчины"},
        "of_decay": {"value_mult": 0.4, "name_suffix": "гниения"},
        "of_the_fool": {"int_penalty": -1, "name_suffix": "глупца"},
        "of_clumsiness": {"dex_penalty": -1, "name_suffix": "неуклюжести"},
        "of_frailty": {"con_penalty": -1, "name_suffix": "хрупкости"},
    },
    "uncommon": {
        "of_precision": {"damage_bonus": 1, "name_suffix": "точности"},
        "of_defense": {"ac_bonus": 1, "name_suffix": "защиты"},
        "of_vitality": {"con_bonus": 1, "name_suffix": "жизненной силы"},
        "of_clarity": {"int_bonus": 1, "name_suffix": "ясности ума"},
        "of_grace": {"dex_bonus": 1, "name_suffix": "грации"},
    },
    "rare": {
        "of_the_guardian": {"ac_bonus": 2, "name_suffix": "хранителя"},
        "of_power": {"str_bonus": 2, "name_suffix": "могущества"},
        "of_wisdom": {"wis_bonus": 2, "name_suffix": "мудрости"},
        "of_the_eagle": {"dex_bonus": 2, "name_suffix": "орла"},
        "of_giant_strength": {"str_bonus": 3, "name_suffix": "силы великанов"},
    },
    "epic": {
        "of_the_dragon": {"damage_bonus": 3, "str_bonus": 2, "name_suffix": "дракона"},
        "of_the_archmage": {"magic_bonus": 3, "int_bonus": 2, "name_suffix": "архимага"},
        "of_immortality": {"con_bonus": 3, "name_suffix": "бессмертия"},
        "of_the_void": {"magic_bonus": 4, "con_penalty": -2, "name_suffix": "пустоты"},
    },
}

RARITY_WEIGHTS = {
    "common": 45,
    "uncommon": 30,
    "rare": 18,
    "epic": 7,
}

# ============================================================
# МАТЕРИАЛЫ И ОПИСАНИЯ ДЛЯ FLAVOR TEXT
# ============================================================

WEAPON_MATERIALS = {
    "bludgeoning": ["дуб", "камень", "сталь", "чугун", "обсидиан", "чёрное железо"],
    "slashing": ["сталь", "дамасская сталь", "метеоритное железо", "серебро", "адамантин"],
    "piercing": ["сталь", "кость дракона", "мифрил", "закалённая сталь", "чёрный металл"],
}

WEAPON_DESCRIPTIONS = {
    "bludgeoning": [
        "Рукоять помнит сотни рук. Большинство из них мертвы. Но не волнуйся.",
        "Вмятина на боевой части. Прежний владелец промахнулся по дракону и попал в стену. Или наоборот.",
        "Обмотка рукояти пахнет потом, страхом и лёгким сожалением. Кто-то очень хотел жить.",
        "Трещина вдоль грани. Следствие удара о голову великана. Великан выжил, оружие — нет.",
        "Каждый удар этим оружием — как аргумент в споре: грубый, но убедительный.",
        "Тяжёлое, неуклюжее, но когда попадает — споры заканчиваются. Навсегда.",
    ],
    "slashing": [
        "Зазубрины на лезвии рассказывают историю. Кости, доспехи и пара особо жёстких буханок хлеба.",
        "Клинок тускло блестит. Точили часто, мыли редко. Кровь — лучшая полировка, говорил мастер.",
        "Узор на гарде почти стёрся. Может, эльфийская вязь, может просто царапины. Спрашивай с убитых.",
        "Гравировка на лезвии: «Возврату не подлежит». Мастер знал что продаёт.",
        "Лезвие острое настолько, что бриться можно. Если не боишься столбняка.",
        "Этот клинок пережил три войны, двух владельцев и одну случайную встречу с точильным камнем.",
    ],
    "piercing": [
        "Погнутое остриё. Кольчуги, чешуя, особо наглая грудная пластина — всё было пробито.",
        "Тёмное пятно на наконечнике. Не ржавчина. Лучше не нюхать.",
        "Рукоять обмотана кожей. Чьей? История умалчивает. Но кожа качественная.",
        "Микроскопическая руна у основания. «Made in Neverwinter» — или что-то вроде того.",
        "Остриё достаточно тонкое чтобы войти в замочную скважину. И достаточно прочное чтобы выйти из спины.",
        "Игла, доросшая до статуса оружия. Пробивает всё, кроме совести.",
    ],
}

ARMOR_DESCRIPTIONS = [
    "На подкладке вышито «Грог был здесь». Грог, судя по дырке от стрелы, ушёл слишком рано.",
    "Заплатки из разной кожи. Владелец штопал доспех чаще чем отношения.",
    "Правое плечо усилено дополнительной пластиной. Левое — нет. Оптимист.",
    "Пахнет кожей, пóтом и победой. Или поражением — запахи похожи.",
    "На нагруднике нацарапано «УДАЧА». Ниже подпись: «Она тебе понадобится.»",
    "Внутри подкладки застрял зуб. Человеческий. Или очень крупного гоблина.",
    "Кто-то пытался пробить этот доспех и потерпел неудачу. Четыре вмятины это подтверждают.",
    "Доспех выглядит так будто его носили три поколения. Так и есть. Только все три умерли в нём.",
]

MISC_DESCRIPTIONS = [
    "Старая, пыльная, непонятная. Как и твои шансы на выживание.",
    "При встряхивании внутри что-то гремит. Сломанный механизм? Проклятие? Кости? Откроем — узнаем.",
    "Покрыта слоем вековой пыли. Пыль может быть древнее чем вся твоя династия.",
    "Слабый запах... чего-то. Магии? Разложения? Сыра? Твой нос не уверен.",
    "На поверхности символы. Ты не знаешь этого языка, но символ в центре похож на «ОПАСНО». Или «СКИДКА».",
    "Предмет тёплый на ощупь. Это не должно быть нормальным. Но ты уже привык.",
    "Выглядит бесполезным. Но лучшие приключения начинались именно с таких находок. И худшие тоже.",
    "Кто-то потратил время на создание этой вещи. Кто-то умер. Вещь осталась. Поэзия.",
]

# ============================================================
# ЛУТ-ТАБЛИЦЫ ПО БИОМАМ
# ============================================================

LOOT_TABLES = {
    "forest": {
        "name": "Лес",
        "common": [
            {"item_key": "forest_mushroom", "name": "Лесной гриб", "qty": "1d4"},
            {"item_key": "medicinal_herb", "name": "Лечебная трава", "qty": "1d3"},
            {"item_key": "berry_bunch", "name": "Горсть ягод", "qty": "1d2"},
            {"item_key": "sturdy_branch", "name": "Крепкая ветка", "qty": 1},
            {"item_key": "animal_pelt", "name": "Шкура зверя", "qty": 1},
            {"item_key": "bird_feather", "name": "Птичье перо", "qty": "1d6"},
            {"item_key": "acorn", "name": "Жёлудь", "qty": "1d8"},
            {"item_key": "spider_silk", "name": "Паучья нить", "qty": 1},
            {"item_key": "moss_clump", "name": "Клочок мха", "qty": 1},
            {"item_key": "wild_honeycomb", "name": "Дикий сот", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "rare_mushroom", "name": "Редкий гриб", "qty": 1},
            {"item_key": "ent_bark", "name": "Кора энта", "qty": 1},
            {"item_key": "fey_dust", "name": "Фейская пыльца", "qty": 1},
            {"item_key": "treant_sap", "name": "Смола тента", "qty": 1},
            {"item_key": "owlbear_claw", "name": "Коготь совомедведя", "qty": 1},
        ],
        "rare": [
            {"item_key": "dryad_tear", "name": "Слеза дриады", "qty": 1},
            {"item_key": "ancient_seed", "name": "Древнее семя", "qty": 1},
            {"item_key": "unicorn_hair", "name": "Волос единорога", "qty": 1},
        ],
    },
    "desert": {
        "name": "Пустыня",
        "common": [
            {"item_key": "cactus_flesh", "name": "Мякоть кактуса", "qty": "1d2"},
            {"item_key": "scorpion_tail", "name": "Хвост скорпиона", "qty": 1},
            {"item_key": "sand_glass", "name": "Пустынное стекло", "qty": 1},
            {"item_key": "dried_lizard", "name": "Сушёная ящерица", "qty": 1},
            {"item_key": "ancient_coin", "name": "Древняя монета", "qty": "1d4"},
            {"item_key": "nomad_scrap", "name": "Обрывок ткани кочевника", "qty": 1},
            {"item_key": "sunbleached_bone", "name": "Выбеленная кость", "qty": "1d2"},
            {"item_key": "salt_crystal", "name": "Соляной кристалл", "qty": 1},
            {"item_key": "sand_worm_scale", "name": "Чешуйка песчаного червя", "qty": 1},
            {"item_key": "desert_flower", "name": "Пустынный цветок", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "mummy_wraps", "name": "Бинты мумии", "qty": 1},
            {"item_key": "phoenix_feather", "name": "Перо феникса", "qty": 1},
            {"item_key": "desert_rose", "name": "Роза пустыни", "qty": 1},
            {"item_key": "djinn_essence", "name": "Эссенция джинна", "qty": 1},
            {"item_key": "sand_worm_tooth", "name": "Зуб песчаного червя", "qty": 1},
        ],
        "rare": [
            {"item_key": "pharaoh_amulet", "name": "Амулет фараона", "qty": 1},
            {"item_key": "sand_of_time", "name": "Песок времени", "qty": 1},
            {"item_key": "sphinx_riddle_stone", "name": "Камень загадок сфинкса", "qty": 1},
        ],
    },
    "dungeon": {
        "name": "Подземелье",
        "common": [
            {"item_key": "broken_sword", "name": "Сломанный меч", "qty": 1},
            {"item_key": "rusty_key", "name": "Ржавый ключ", "qty": 1},
            {"item_key": "torch_stub", "name": "Огарок факела", "qty": "1d2"},
            {"item_key": "rat_tail", "name": "Крысиный хвост", "qty": "1d3"},
            {"item_key": "cobweb", "name": "Паутина", "qty": 1},
            {"item_key": "bone_fragment", "name": "Обломок кости", "qty": "1d4"},
            {"item_key": "ancient_coin", "name": "Древняя монета", "qty": "1d6"},
            {"item_key": "moldy_bread", "name": "Заплесневелый хлеб", "qty": 1},
            {"item_key": "loose_stone", "name": "Шатающийся камень", "qty": 1},
            {"item_key": "shiny_pebble", "name": "Блестящий камешек", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "enchanted_torch", "name": "Зачарованный факел", "qty": 1},
            {"item_key": "skeleton_key", "name": "Отмычка", "qty": 1},
            {"item_key": "ghost_residue", "name": "Призрачный осадок", "qty": 1},
            {"item_key": "bat_guano", "name": "Гуано летучей мыши", "qty": 1},
            {"item_key": "trap_mechanism", "name": "Механизм ловушки", "qty": 1},
        ],
        "rare": [
            {"item_key": "lich_phylactery_shard", "name": "Осколок филактерии лича", "qty": 1},
            {"item_key": "dragon_scale", "name": "Чешуя дракона", "qty": 1},
            {"item_key": "ancient_tome_page", "name": "Страница древнего фолианта", "qty": 1},
        ],
    },
    "mountains": {
        "name": "Горы",
        "common": [
            {"item_key": "iron_ore", "name": "Железная руда", "qty": "1d3"},
            {"item_key": "eagle_feather", "name": "Орлиное перо", "qty": 1},
            {"item_key": "mountain_goat_horn", "name": "Рог горного козла", "qty": 1},
            {"item_key": "geode_fragment", "name": "Осколок жеоды", "qty": 1},
            {"item_key": "climbing_piton", "name": "Скальный крюк", "qty": "1d2"},
            {"item_key": "frostberry", "name": "Морозная ягода", "qty": "1d3"},
            {"item_key": "stone_chip", "name": "Каменный осколок", "qty": "1d4"},
            {"item_key": "mountain_herb", "name": "Горная трава", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "silver_vein", "name": "Серебряная жила", "qty": 1},
            {"item_key": "gryphon_feather", "name": "Перо грифона", "qty": 1},
            {"item_key": "thunder_egg", "name": "Громовое яйцо", "qty": 1},
            {"item_key": "giant_eagle_egg", "name": "Яйцо гигантского орла", "qty": 1},
            {"item_key": "dwarven_gear", "name": "Дварфийская шестерня", "qty": 1},
        ],
        "rare": [
            {"item_key": "mithril_ore", "name": "Мифриловая руда", "qty": 1},
            {"item_key": "giant_rune", "name": "Руна великана", "qty": 1},
            {"item_key": "roc_feather", "name": "Перо руха", "qty": 1},
        ],
    },
    "swamp": {
        "name": "Болото",
        "common": [
            {"item_key": "bog_herb", "name": "Болотная трава", "qty": "1d3"},
            {"item_key": "frog_leg", "name": "Лягушачья лапка", "qty": "1d4"},
            {"item_key": "marsh_mud", "name": "Болотная грязь", "qty": 1},
            {"item_key": "willow_bark", "name": "Ивовая кора", "qty": 1},
            {"item_key": "leech", "name": "Пиявка", "qty": "1d3"},
            {"item_key": "bog_lantern", "name": "Болотный огонёк", "qty": 1},
            {"item_key": "cattail", "name": "Рогоз", "qty": "1d4"},
            {"item_key": "rotten_wood", "name": "Гнилое дерево", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "hag_hair", "name": "Волос ведьмы", "qty": 1},
            {"item_key": "black_lotus", "name": "Чёрный лотос", "qty": 1},
            {"item_key": "ghost_orb", "name": "Призрачная сфера", "qty": 1},
            {"item_key": "swamp_gas_vial", "name": "Пузырёк болотного газа", "qty": 1},
            {"item_key": "crocodile_tooth", "name": "Зуб крокодила", "qty": 1},
        ],
        "rare": [
            {"item_key": "lich_moss", "name": "Мох лича", "qty": 1},
            {"item_key": "black_dragon_scale", "name": "Чешуя чёрного дракона", "qty": 1},
            {"item_key": "bog_mummy_heart", "name": "Сердце болотной мумии", "qty": 1},
        ],
    },
    "coast": {
        "name": "Побережье",
        "common": [
            {"item_key": "seashell", "name": "Ракушка", "qty": "1d6"},
            {"item_key": "driftwood", "name": "Плавник", "qty": 1},
            {"item_key": "seagull_feather", "name": "Перо чайки", "qty": "1d3"},
            {"item_key": "crab_shell", "name": "Панцирь краба", "qty": 1},
            {"item_key": "dried_seaweed", "name": "Сушёные водоросли", "qty": "1d2"},
            {"item_key": "glass_shard", "name": "Осколок стекла", "qty": "1d4"},
            {"item_key": "fishing_hook", "name": "Рыболовный крючок", "qty": 1},
            {"item_key": "smooth_pebble", "name": "Гладкий камешек", "qty": "1d4"},
        ],
        "uncommon": [
            {"item_key": "pearl", "name": "Жемчужина", "qty": 1},
            {"item_key": "coral_piece", "name": "Кусок коралла", "qty": 1},
            {"item_key": "mermaid_scale", "name": "Чешуя русалки", "qty": 1},
            {"item_key": "message_in_bottle", "name": "Послание в бутылке", "qty": 1},
            {"item_key": "shark_tooth", "name": "Зуб акулы", "qty": 1},
        ],
        "rare": [
            {"item_key": "kraken_ink", "name": "Чернила кракена", "qty": 1},
            {"item_key": "triton_trident_fragment", "name": "Осколок трезубца тритона", "qty": 1},
            {"item_key": "aboleth_eye", "name": "Глаз аболета", "qty": 1},
        ],
    },
    "urban": {
        "name": "Город",
        "common": [
            {"item_key": "stale_bread", "name": "Чёрствый хлеб", "qty": 1},
            {"item_key": "copper_coin", "name": "Медная монета", "qty": "1d8"},
            {"item_key": "nails", "name": "Гвозди", "qty": "1d6"},
            {"item_key": "candle_stub", "name": "Огарок свечи", "qty": "1d3"},
            {"item_key": "empty_vial", "name": "Пустой пузырёк", "qty": 1},
            {"item_key": "scribbled_note", "name": "Исписанная записка", "qty": 1},
            {"item_key": "cheap_ale", "name": "Дешёвый эль", "qty": 1},
            {"item_key": "torn_ticket", "name": "Оторванный билет", "qty": 1},
            {"item_key": "matchbox", "name": "Коробок спичек", "qty": 1},
            {"item_key": "soap_bar", "name": "Кусок мыла", "qty": 1},
        ],
        "uncommon": [
            {"item_key": "silver_ring", "name": "Серебряное кольцо", "qty": 1},
            {"item_key": "guild_insignia", "name": "Значок гильдии", "qty": 1},
            {"item_key": "thieves_cant_scroll", "name": "Свиток с воровским жаргоном", "qty": 1},
            {"item_key": "noble_silk", "name": "Шёлк дворянина", "qty": 1},
            {"item_key": "poison_vial", "name": "Пузырёк с ядом", "qty": 1},
        ],
        "rare": [
            {"item_key": "assassin_ring", "name": "Кольцо ассасина", "qty": 1},
            {"item_key": "noble_deed", "name": "Дворянская грамота", "qty": 1},
            {"item_key": "arcane_lockbox", "name": "Магическая шкатулка", "qty": 1},
        ],
    },
}

# ============================================================
# ПРЕДМЕТЫ, СВЯЗАННЫЕ С ПРЕДЫСТОРИЯМИ (дополнительные)
# ============================================================

BACKSTORY_ITEMS = {
    "кузнец": [
        {"item_key": "smith_hammer", "name": "Молот кузнеца", "item_type": "tool", "item_subtype": "smithing", "weight_lb": 3, "value_gp": 2, "slot": "inventory"},
        {"item_key": "forged_knife", "name": "Кованый нож", "item_type": "weapon", "item_subtype": "simple_melee", "damage": "1d4+1", "damage_type": "slashing", "weight_lb": 1, "value_gp": 3, "slot": "main_hand", "notes": "Кузнец знает каждый изгиб этого клинка."},
    ],
    "охотник": [
        {"item_key": "hunting_trap", "name": "Охотничий капкан", "item_type": "gear", "item_subtype": "trap", "weight_lb": 5, "value_gp": 5, "slot": "inventory"},
        {"item_key": "animal_bone_whistle", "name": "Свисток из кости", "item_type": "gear", "item_subtype": "tool", "weight_lb": 0.1, "value_gp": 1, "slot": "inventory"},
    ],
    "травник": [
        {"item_key": "herb_pouch", "name": "Мешочек с травами", "item_type": "gear", "item_subtype": "herbalism", "weight_lb": 1, "value_gp": 3, "slot": "inventory"},
        {"item_key": "mortar_pestle", "name": "Ступка и пестик", "item_type": "tool", "item_subtype": "alchemy", "weight_lb": 2, "value_gp": 5, "slot": "inventory"},
    ],
    "вор": [
        {"item_key": "concealed_dagger", "name": "Скрытый кинжал", "item_type": "weapon", "item_subtype": "simple_melee", "damage": "1d4", "damage_type": "piercing", "properties": ["light", "finesse"], "weight_lb": 0.5, "value_gp": 5, "slot": "main_hand", "notes": "Лезвие спрятано в складках одежды."},
        {"item_key": "lockpick_set", "name": "Набор отмычек", "item_type": "tool", "item_subtype": "thieves", "weight_lb": 0.5, "value_gp": 15, "slot": "inventory"},
    ],
    "солдат": [
        {"item_key": "lucky_charm", "name": "Счастливый талисман", "item_type": "gear", "item_subtype": "trinket", "weight_lb": 0.1, "value_gp": 1, "slot": "inventory", "notes": "Талисман, прошедший с вами не одно сражение."},
        {"item_key": "unit_insignia", "name": "Знак отличия", "item_type": "gear", "item_subtype": "trinket", "weight_lb": 0.1, "value_gp": 0, "slot": "inventory", "notes": "Эмблема вашего подразделения."},
    ],
    "мореплаватель": [
        {"item_key": "compass", "name": "Компас", "item_type": "tool", "item_subtype": "navigation", "weight_lb": 0.5, "value_gp": 15, "slot": "inventory"},
        {"item_key": "ship_in_bottle", "name": "Корабль в бутылке", "item_type": "gear", "item_subtype": "trinket", "weight_lb": 1, "value_gp": 3, "slot": "inventory"},
    ],
    "торговец": [
        {"item_key": "merchant_scale", "name": "Купеческие весы", "item_type": "tool", "item_subtype": "weighing", "weight_lb": 1, "value_gp": 5, "slot": "inventory"},
        {"item_key": "ledger_book", "name": "Учётная книга", "item_type": "gear", "item_subtype": "book", "weight_lb": 2, "value_gp": 2, "slot": "inventory"},
    ],
    "учёный": [
        {"item_key": "magnifying_glass", "name": "Увеличительное стекло", "item_type": "tool", "item_subtype": "research", "weight_lb": 0.2, "value_gp": 20, "slot": "inventory"},
        {"item_key": "research_notes", "name": "Исследовательские заметки", "item_type": "gear", "item_subtype": "book", "weight_lb": 1, "value_gp": 2, "slot": "inventory"},
    ],
}

# ============================================================
# ФУНКЦИИ ГЕНЕРАЦИИ
# ============================================================

def parse_dice(dice_str: str) -> int:
    """Распарсить строку вроде '1d6' или '2d4' в число."""
    if isinstance(dice_str, int):
        return dice_str
    m = re.match(r"(\d+)d(\d+)", str(dice_str))
    if m:
        count, sides = int(m.group(1)), int(m.group(2))
        return sum(random.randint(1, sides) for _ in range(count))
    return 1


def roll_rarity() -> str:
    """Выбросить редкость предмета по весам."""
    choices = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    return random.choices(choices, weights=weights, k=1)[0]


def _roll_affix(pool: dict) -> tuple[str, dict]:
    """Случайный префикс/суффикс из пула: (ключ, словарь аффикса)."""
    key = random.choice(list(pool.keys()))
    return key, pool[key]


def _loot_flavor(item_type: str, modifiers: dict) -> str:
    """Описание предмета по типу."""
    if item_type in ("weapon",):
        dmg_type = modifiers.get("damage_type", "slashing")
        descs = WEAPON_DESCRIPTIONS.get(dmg_type, WEAPON_DESCRIPTIONS["slashing"])
        return random.choice(descs)
    if item_type == "armor":
        return random.choice(ARMOR_DESCRIPTIONS)
    return random.choice(MISC_DESCRIPTIONS)


def generate_modifiers(rarity: str, item_type: str) -> dict:
    """
    Сгенерировать рандомные модификаторы для предмета.
    Возвращает dict с бонусами/пенальти и flavour.
    """
    prefix_pool = ITEM_PREFIXES.get(rarity, ITEM_PREFIXES["common"])
    suffix_pool = ITEM_SUFFIXES.get(rarity, ITEM_SUFFIXES["common"])

    modifiers = {}
    flavor_parts = []

    # 40% шанс получить префикс
    if random.random() < 0.4:
        prefix_key, prefix = _roll_affix(prefix_pool)
        _merge_affix_bonuses(modifiers, flavor_parts, prefix)
        modifiers["prefix"] = prefix_key

    # 25% шанс получить суффикс
    if random.random() < 0.25:
        suffix_key, suffix = _roll_affix(suffix_pool)
        _merge_affix_bonuses(modifiers, flavor_parts, suffix)
        modifiers["suffix"] = suffix_key

    # Генерируем описание
    modifiers["flavor"] = _loot_flavor(item_type, modifiers)
    modifiers["rarity"] = rarity

    # Объединяем имя
    if flavor_parts:
        modifiers["name_affix"] = " ".join(flavor_parts)

    return modifiers


def _merge_affix_bonuses(modifiers: dict, flavor_parts: list, affix: dict) -> None:
    """Слить бонусы аффикса: name_* → flavor, value_mult/break_chance → пропуск,
    остальное — суммирование числовых ключей."""
    for k, v in affix.items():
        if k in ("name_prefix", "name_suffix"):
            flavor_parts.append(v)
        elif k in ("value_mult", "break_chance"):
            continue
        elif k in modifiers and isinstance(v, (int, float)) and isinstance(modifiers[k], (int, float)):
            modifiers[k] += v
        else:
            modifiers[k] = v


# Алиасы биомов — чтобы не плодить пустые ответы
BIOME_ALIASES = {
    "cave": "dungeon",
    "ruins": "dungeon",
    "tundra": "mountains",
    "plains": "forest",
    "jungle": "forest",
    "underdark": "dungeon",
    "crypt": "dungeon",
    "graveyard": "swamp",
    "cellar": "dungeon",
    "sewer": "swamp",
}


def generate_loot(biome: str, count: int = 1) -> list[dict]:
    """
    Сгенерировать лут для указанного биома.
    Возвращает список предметов.
    """
    # Пробуем прямой поиск, затем алиасы, затем default
    table = LOOT_TABLES.get(biome)
    if not table:
        aliased = BIOME_ALIASES.get(biome)
        if aliased:
            table = LOOT_TABLES.get(aliased)
    if not table:
        table = LOOT_TABLES.get("dungeon")

    items = []
    for _ in range(count):
        rarity = roll_rarity()
        pool = table.get(rarity, table.get("common", []))
        if not pool:
            continue

        template = random.choice(pool)
        qty = parse_dice(template.get("qty", 1))

        item = {
            "item_key": template["item_key"],
            "item_name": template["name"],
            "item_type": "loot",
            "item_subtype": biome,
            "qty": qty,
            "slot": "inventory",
            "equipped": 0,
            "notes": f"Найдено в локации: {table['name']}",
        }

        # Добавляем модификаторы для необычных предметов
        if rarity != "common":
            item["modifiers"] = generate_modifiers(rarity, "misc")

        items.append(item)

    return items


def detect_biome_from_text(scene_text: str) -> Optional[str]:
    """
    Попытаться определить биом по тексту сцены.
    Использует ключевые слова с границами слов (\\b).
    """
    import re

    text_lower = scene_text.lower()

    biome_keywords = {
        "forest": [
            "лес", "дерево", "деревья", "чаща", "дубрава", "роща", "ель",
            "сосна", "листва", "ветка", "куст", "заросли", "лесной", "чащоба",
            "forest", "tree", "wood", "grove",
        ],
        "desert": [
            "пустыня", "песок", "бархан", "кактус", "оазис", "зной",
            "песчаный", "пустошь", "жара", "суховей",
            "desert", "sand", "cactus", "oasis",
        ],
        "dungeon": [
            "подземелье", "катакомбы", "гробница", "склеп", "пещера",
            "туннель", "шахта", "подвал", "темница", "коридор",
            "dungeon", "tomb", "cave", "catacomb", "crypt", "tunnel",
        ],
        "mountains": [
            "гора", "горы", "скала", "ущелье", "пик", "вершина",
            "хребет", "перевал", "обрыв", "каменный",
            "mountain", "cliff", "peak", "ridge",
        ],
        "swamp": [
            "болото", "топь", "трясина", "гниль", "тина", "заводь",
            "камыш", "мох", "плесень", "сырость",
            "swamp", "bog", "marsh", "mud",
        ],
        "coast": [
            "берег", "море", "океан", "пляж", "пристань", "гавань",
            "волна", "прибой", "залив", "бухта", "остров",
            "coast", "sea", "ocean", "beach", "shore", "bay", "island",
        ],
        "urban": [
            "город", "таверн", "улица", "рынок", "лавка", "гильдия",
            "площадь", "академия", "храм", "замок", "деревня", "посёл",
            "city", "town", "tavern", "inn", "market", "shop", "guild",
        ],
    }

    scores = {}
    for biome, keywords in biome_keywords.items():
        score = sum(1 for kw in keywords if re.search('\\b' + re.escape(kw), text_lower))
        if score > 0:
            scores[biome] = score

    if scores:
        return max(scores, key=scores.get)
    return None


def get_backstory_items(backstory: str, class_name: str = "") -> list[dict]:
    """
    Извлечь предметы на основе текста предыстории.
    Ищет ключевые слова в тексте и подбирает подходящие предметы.
    """
    text_lower = backstory.lower()
    items = []

    for keyword, item_list in BACKSTORY_ITEMS.items():
        if keyword in text_lower:
            # 50% шанс получить предмет из каждой подходящей категории
            for item_template in item_list:
                if random.random() < 0.5:
                    item = dict(item_template)
                    item["qty"] = 1
                    item["equipped"] = 0
                    item["slot"] = item.get("slot", "inventory")
                    item["notes"] = item.get("notes", f"Из предыстории: {keyword}")
                    items.append(item)

    return items
