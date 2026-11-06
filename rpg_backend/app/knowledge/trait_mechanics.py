"""
Механики расовых черт для Mixed Heritage.
Автоматически сгенерировано из описаний MIXED_HERITAGE_CONFIG.
Формат: TRAIT_MECHANICS["Раса"]["Название черты"] = {механики}

Поля механик (все опциональны):
  hp_bonus: int                — +HP за уровень
  ac: str                      — формула ("13 + dex") или число ("17")
  ac_bonus: int                — плоский бонус к AC
  resistances: [str]           — типы урона; "*choice" = зависит от выбора
  damage_immunity: [str]       — иммунитет к урону
  condition_immunity: [str]    — иммунитет к состояниям
  darkvision: int              — дальность в футах
  skills: [str]                — фиксированное владение навыками
  skill_choices: {count: int, from: [str]}  — выбор навыка
  cantrips: [str]              — заговоры
  spells: [{name, info}]       — заклинания (не заговоры)
  speeds: {fly/climb/swim: int}— доп. скорости
  natural_weapons: [{name, damage, stat, type}] — естественное оружие
  save_advantage: [str]        — преимущество на спасброски
  breath_hold: int             — минуты задержки дыхания
  temp_hp: bool                — даёт временные хиты
"""

# noqa: E501
TRAIT_MECHANICS = {
  "Ааракокра": {
    "Полёт": {
      "speeds": {
        "fly": 50
      }
    },
    "Когти": {
      "natural_weapons": [
        {
          "name": "Когти",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Ветреный зов": {
      "skills": [
        "perception"
      ]
    }
  },
  "Аасимар": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Небесное сопротивление": {
      "resistances": [
        "radiant",
        "necrotic"
      ]
    },
    "Носитель света": {
      "cantrips": [
        "light"
      ]
    }
  },
  "Багбир": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Скрытность": {
      "skills": [
        "stealth"
      ]
    }
  },
  "Ведалкен": {
    "Бесстрастие ведалкенов": {
      "save_advantage": [
        "int",
        "wis",
        "cha"
      ]
    },
    "Неустанная скрупулёзность": {
      "skills": [
        "medicine",
        "arcana",
        "history",
        "investigation",
        "performance",
        "sleight_of_hand"
      ]
    }
  },
  "Ведьмовская кровь": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Ведьмовская магия": {
      "spells": [
        {
          "name": "Маскировка",
          "info": "Вы можете накладывать заклинания Маскировка и Сглаз. После использования каждого заклинания этой чер"
        },
        {
          "name": "Сглаз",
          "info": "Вы можете накладывать заклинания Маскировка и Сглаз. После использования каждого заклинания этой чер"
        }
      ]
    }
  },
  "Вердан": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Убедительный": {
      "skills": [
        "persuasion"
      ]
    },
    "Телепатическая проницательность": {
      "save_advantage": [
        "wis",
        "cha"
      ]
    },
    "Чёрная кровь": {
      "resistances": [
        "poison"
      ],
      "save_advantage": [
        "vs_poison"
      ]
    }
  },
  "Возрождённый": {
    "Наследие предков": {
      "skill_choices": {
        "count": 2,
        "from": [
          "*any"
        ]
      }
    },
    "Бессмертная природа": {
      "resistances": [
        "poison"
      ],
      "save_advantage": [
        "vs_poison",
        "vs_death",
        "vs_disease"
      ]
    }
  },
  "Гибрид Симиков": {
    "Тёмное зрение": {
      "darkvision": 60
    }
  },
  "Гит": {
    "Ментальная стойкость": {
      "save_advantage": [
        "vs_fear",
        "vs_charm"
      ]
    },
    "Псионические способности": {
      "cantrips": [
        "mage_hand"
      ]
    },
    "Подрасы: Гитъянки и Гитцераи": {
      "cantrips": [
        "mage_hand"
      ]
    }
  },
  "Гном": {
    "Ночное зрение": {
      "darkvision": 60
    },
    "Гномья хитрость": {
      "save_advantage": [
        "int",
        "wis",
        "cha",
        "vs_spells"
      ]
    },
    "Гномья родословная": {
      "cantrips": [
        "minor_illusion",
        "speak_with_animals",
        "mending"
      ]
    }
  },
  "Гоблин": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Ярость маленьких": {
      "damage_bonus_pb": True
    },
    "Шустрый побег": {
      "bonus_action": [
        "disengage",
        "hide"
      ]
    }
  },
  "Голиаф": {
    "Крупный размер": {
      "save_advantage": [
        "str"
      ]
    },
    "Могучее телосложение": {
      "save_advantage": [
        "vs_grapple"
      ]
    },
    "Наследие великанов": {
      "temp_hp": True
    }
  },
  "Грунг": {
    "Древесный образ жизни": {
      "speeds": {
        "climb": 25
      }
    }
  },
  "Дампир": {
    "Тёмное зрение 60 футов": {
      "darkvision": 60
    },
    "Паучий карабкатель": {
      "speeds": {
        "climb": 35
      }
    },
    "Вампирский укус": {
      "natural_weapons": [
        {
          "name": "Вампирский укус",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    }
  },
  "Дварф": {
    "Ночное зрение": {
      "darkvision": 120
    },
    "Стойкость дварфа": {
      "resistances": [
        "poison"
      ],
      "save_advantage": [
        "vs_poison"
      ]
    },
    "Живучесть дварфа": {
      "hp_bonus": 1
    }
  },
  "Дженази": {
    "Слияние со стихией": {
      "darkvision": 60,
      "resistances": [
        "fire"
      ]
    }
  },
  "Драконорождённый": {
    "Устойчивость к урону": {
      "resistances": [
        "*choice"
      ]
    },
    "Ночное зрение": {
      "darkvision": 60
    }
  },
  "Зайцегон": {
    "Заячье сердце": {
      "initiative_bonus": "pb"
    },
    "Длинные уши": {
      "skills": [
        "perception"
      ]
    },
    "Сильные ноги": {
      "reaction_save": True
    }
  },
  "Калаштар": {
    "Двойственный разум": {
      "save_advantage": [
        "wis"
      ]
    },
    "Ментальная дисциплина": {
      "resistances": [
        "psychic"
      ]
    }
  },
  "Кендер": {
    "Бесстрашие": {
      "save_advantage": [
        "vs_fear"
      ]
    },
    "Любопытство кендеров": {
      "skill_choices": {
        "count": 1,
        "from": [
          "stealth",
          "survival",
          "insight",
          "sleight_of_hand",
          "investigation"
        ]
      }
    }
  },
  "Кенку": {
    "Воронья тренировка": {
      "skills": [
        "stealth",
        "deception",
        "acrobatics",
        "sleight_of_hand"
      ]
    }
  },
  "Кентавр": {
    "Копыта": {
      "natural_weapons": [
        {
          "name": "Копыта",
          "damage": "1d4",
          "stat": "STR",
          "type": "bludgeoning"
        }
      ]
    },
    "Выживший": {
      "skills": [
        "survival",
        "nature",
        "medicine",
        "animal_handling"
      ]
    }
  },
  "Кобольд": {
    "Тёмное зрение": {
      "darkvision": 60
    }
  },
  "Кованый": {
    "Стойкость кованых": {
      "resistances": [
        "poison"
      ],
      "save_advantage": [
        "vs_poison",
        "vs_disease"
      ]
    },
    "Встроенная защита": {
      "ac_bonus": 1
    },
    "Специальная сборка": {
      "skill_choices": {
        "count": 1,
        "from": [
          "*any"
        ]
      }
    }
  },
  "Леонин": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Когти": {
      "natural_weapons": [
        {
          "name": "Когти",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Охотничьи инстинкты": {
      "skill_choices": {
        "count": 1,
        "from": [
          "perception",
          "intimidation",
          "athletics",
          "survival"
        ]
      }
    }
  },
  "Локата": {
    "Естественный пловец": {
      "speeds": {
        "swim": 30
      }
    },
    "Естественный доспех": {
      "ac": "12 + dex"
    },
    "Наблюдательность": {
      "skills": [
        "perception",
        "survival"
      ]
    }
  },
  "Локсодон": {
    "Мощное телосложение": {
      "save_advantage": [
        "vs_grapple"
      ]
    },
    "Естественный доспех": {
      "ac": "12 + con"
    },
    "Хобот": {
      "natural_weapons": [
        {
          "name": "Хобот",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Спокойствие локсодона": {
      "save_advantage": [
        "vs_fear",
        "vs_charm"
      ]
    }
  },
  "Людоящер": {
    "Естественный доспех": {
      "ac": "13 + dex"
    },
    "Укус": {
      "natural_weapons": [
        {
          "name": "Укус",
          "damage": "1d6",
          "stat": "STR",
          "type": "piercing"
        }
      ]
    },
    "Голодные челюсти": {
      "temp_hp": True
    },
    "Задержка дыхания": {
      "breath_hold": 15
    }
  },
  "Минотавр": {
    "Рога": {
      "natural_weapons": [
        {
          "name": "Рога",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Сокрушительные рога": {
      "natural_weapons": [
        {
          "name": "Сокрушительные рога",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Впечатляющий вид": {
      "skill_choices": {
        "count": 1,
        "from": [
          "intimidation",
          "persuasion"
        ]
      }
    }
  },
  "Орк": {
    "Выброс адреналина": {
      "bonus_action": [
        "dash"
      ]
    },
    "Несгибаемая стойкость": {
      "relentless": True
    },
    "Ночное зрение": {
      "darkvision": 120
    }
  },
  "Полуорк": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Непоколебимая стойкость": {
      "relentless": True
    },
    "Устрашение": {
      "skills": [
        "intimidation"
      ]
    }
  },
  "Полурослик": {
    "Храбрость": {
      "save_advantage": [
        "vs_fear"
      ]
    }
  },
  "Полуэльф": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Наследие фей": {
      "save_advantage": [
        "vs_charm"
      ]
    }
  },
  "Сатир": {
    "Таран": {
      "natural_weapons": [
        {
          "name": "Таран",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Гуляка": {
      "skill_choices": {
        "count": 1,
        "from": [
          "persuasion",
          "performance"
        ]
      }
    },
    "Сопротивление магии": {
      "save_advantage": [
        "vs_spells"
      ]
    }
  },
  "Совлин": {
    "Полёт": {
      "speeds": {
        "fly": 30
      }
    },
    "Тёмное зрение 120 футов": {
      "darkvision": 120
    },
    "Бесшумные перья": {
      "skills": [
        "stealth"
      ]
    }
  },
  "Табакси": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Кошачьи когти": {
      "speeds": {
        "climb": 20
      },
      "natural_weapons": [
        {
          "name": "Кошачьи когти",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Кошачьи способности": {
      "skills": [
        "perception",
        "stealth"
      ]
    }
  },
  "Тифлинг": {
    "Ночное зрение": {
      "darkvision": 60
    },
    "Наследие бестий": {
      "resistances": [
        "fire"
      ],
      "cantrips": [
        "poison_spray",
        "fire_bolt",
        "ray_of_sickness"
      ]
    },
    "Сверхъестественная сила": {
      "cantrips": [
        "thaumaturgy"
      ]
    }
  },
  "Тортл": {
    "Природный доспех": {
      "ac": "17"
    },
    "Панцирная защита": {
      "save_advantage": [
        "str"
      ]
    },
    "Когти": {
      "natural_weapons": [
        {
          "name": "Когти",
          "damage": "1d4",
          "stat": "STR",
          "type": "slashing"
        }
      ]
    },
    "Инстинкт выживания": {
      "skills": [
        "survival"
      ]
    }
  },
  "Тритон": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Стражи глубин": {
      "resistances": [
        "cold"
      ]
    }
  },
  "Фирболг": {
    "Незримая поступь": {
      "bonus_action": [
        "invisibility"
      ]
    },
    "Язык зверей и листвы": {
      "save_advantage": [
        "cha"
      ]
    }
  },
  "Фэйри": {
    "Магия фей": {
      "spells": [
        {
          "name": "Огонь фей",
          "info": "С 3 уровня вы можете накладывать заклинание Огонь фей. С 5 уровня — заклинание Увеличение/уменьшение"
        },
        {
          "name": "Увеличение",
          "info": "С 3 уровня вы можете накладывать заклинание Огонь фей. С 5 уровня — заклинание Увеличение/уменьшение"
        }
      ]
    }
  },
  "Хобгоблин": {
    "Тёмное зрение": {
      "darkvision": 60
    }
  },
  "Чейнджлинг": {
    "Инстинкты чейнджлинга": {
      "skill_choices": {
        "count": 2,
        "from": [
          "*any"
        ]
      }
    }
  },
  "Человек": {
    "Умелость": {
      "skill_choices": {
        "count": 1,
        "from": [
          "*any"
        ]
      }
    }
  },
  "Шифтер": {
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Смена формы": {
      "temp_hp": True
    }
  },
  "Эльф": {
    "Ночное зрение": {
      "darkvision": 60
    },
    "Острое восприятие": {
      "skill_choices": {
        "count": 1,
        "from": [
          "perception",
          "survival",
          "insight"
        ]
      }
    },
    "Эльфийская родословная": {
      "darkvision": 120,
      "cantrips": [
        "prestidigitation",
        "dancing_lights",
        "faerie_fire",
        "druidcraft",
        "produce_flame"
      ]
    },
    "Наследие фей": {
      "save_advantage": [
        "vs_charm"
      ]
    }
  },
  "Юань-ти": {
    "Иммунитет к яду": {
      "damage_immunity": [
        "poison"
      ],
      "condition_immunity": [
        "poisoned"
      ]
    },
    "Тёмное зрение": {
      "darkvision": 60
    },
    "Магическая защита": {
      "save_advantage": [
        "vs_spells"
      ]
    },
    "Врождённое колдовство": {
      "cantrips": [
        "poison_spray"
      ]
    }
  }
}
