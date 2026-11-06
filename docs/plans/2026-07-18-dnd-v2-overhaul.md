# D&D AI Master v2 — Полная переработка

> **Для Hermes:** используй `subagent-driven-development` для реализации task-by-task.

**Цель:** Превратить простой чат-бот в полноценного AI-мастера D&D 5e с аккаунтами, персонажами, базой знаний правил и умной системой бросков кубиков.

**Архитектура:** SQLite для пользователей и персонажей (одна БД в контейнере), расширенный system prompt с SRD-правилами, кубики как first-class сообщения в API, парсинг AI-подсказок на клиенте для tappable дайсов.

**Tech Stack:** FastAPI + SQLite (aiosqlite) + ForgetAPI (DeepSeek v4 Flash) / Flutter + Riverpod + shared_preferences

---

## Этап 1: База знаний D&D 5e

### Task 1.1: Создать модуль knowledge_base.py с SRD-правилами

**Objective:** Добавить структурированную базу знаний D&D 5e SRD в бэкенд

**Файлы:**
- Создать: `rpg_backend/app/knowledge/__init__.py`
- Создать: `rpg_backend/app/knowledge/srd_rules.py`

**Что включить (компактно, на русском):**
- Базовые механики: d20 + модификатор vs DC, преимущество/помеха
- 6 характеристик и их модификаторы: (-5..+5 от 1..30)
- Навыки: Athletics, Acrobatics, Stealth, Arcana, Perception, Persuasion и т.д. — привязаны к характеристикам
- Спасброски: к каждой характеристике
- Боевая система: инициатива (d20+DEX), атака (d20+STR/DEX+prof vs AC), урон (оружие + модификатор)
- Состояния: grappled, prone, poisoned, frightened, invisible и т.д.
- Классы сложности: Very Easy (5) → Nearly Impossible (30)
- Критический успех (20) / провал (1) на атаках и спасбросках

```python
# srd_rules.py — компактный dict
DND_SRD = {
    "abilities": {
        "strength": {"skills": ["athletics"], "save": "strength"},
        "dexterity": {"skills": ["acrobatics", "sleight_of_hand", "stealth"], "save": "dexterity"},
        ...
    },
    "combat": {
        "attack_roll": "d20 + ability_mod + proficiency_bonus vs AC",
        "damage_types": ["slashing", "piercing", "bludgeoning", "fire", "cold", ...],
        ...
    },
    "difficulty_classes": {
        "very_easy": 5, "easy": 10, "medium": 15, "hard": 20,
        "very_hard": 25, "nearly_impossible": 30
    },
    ...
}
```

**Проверка:** `python -c "from app.knowledge.srd_rules import DND_SRD; print(len(DND_SRD))"` — не пусто.

---

### Task 1.2: Интегрировать knowledge base в system prompt

**Objective:** AI-мастер получает правила D&D в system prompt

**Файлы:**
- Изменить: `rpg_backend/app/config.py` — `system_prompt`
- Изменить: `rpg_backend/app/services/chat_service.py` — `_build_system_prompt()`

**Логика:**
```python
def _build_system_prompt(self, character: dict | None = None) -> str:
    from app.knowledge.srd_rules import format_srd_for_prompt
    prompt = settings.system_prompt
    prompt += "\n\n" + format_srd_for_prompt()  # компактный текст
    if character:
        prompt += "\n\n" + format_character_for_prompt(character)
    return prompt
```

Функция `format_srd_for_prompt()` превращает DND_SRD в текстовый справочник (~2000-3000 токенов), который AI может использовать.

**Проверка:** отправить сообщение "как работает атака?" — AI должен ответить по правилам 5e.

---

## Этап 2: Авторизация и персонажи

### Task 2.1: Добавить aiosqlite и создать схему БД

**Objective:** SQLite база для пользователей и персонажей

**Файлы:**
- Создать: `rpg_backend/app/db.py` — подключение к SQLite через aiosqlite
- Создать: `rpg_backend/app/db_schema.sql` — CREATE TABLE

**Таблицы:**
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,  -- UUID
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE characters (
    id TEXT PRIMARY KEY,  -- UUID
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    race TEXT NOT NULL,
    class_name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    stats TEXT NOT NULL,  -- JSON: {"str":15,"dex":12,...}
    hp_max INTEGER NOT NULL,
    hp_current INTEGER NOT NULL,
    ac INTEGER NOT NULL,
    equipment TEXT DEFAULT '[]',  -- JSON array
    background TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**Проверка:** `python -c "import asyncio; from app.db import init_db; asyncio.run(init_db())"` — создаёт rpg.db.

---

### Task 2.2: Реализовать auth endpoints (register/login)

**Objective:** JWT-авторизация

**Файлы:**
- Создать: `rpg_backend/app/auth.py` — хеширование паролей (bcrypt) + JWT
- Создать: `rpg_backend/app/api/v1/auth.py` — router `/api/v1/auth/register`, `/api/v1/auth/login`
- Изменить: `rpg_backend/app/models.py` — добавить `RegisterRequest`, `LoginRequest`, `AuthResponse`

**Эндпоинты:**
```
POST /api/v1/auth/register  {"username": "...", "password": "..."} → {"token": "...", "user_id": "..."}
POST /api/v1/auth/login     {"username": "...", "password": "..."} → {"token": "...", "user_id": "..."}
```

**Проверка:** curl зарегистрироваться → получить токен → curl /api/v1/characters с токеном.

---

### Task 2.3: Реализовать character CRUD

**Objective:** Создание, чтение, обновление персонажа

**Файлы:**
- Создать: `rpg_backend/app/api/v1/characters.py` — router
- Изменить: `rpg_backend/app/models.py` — добавить `CharacterCreate`, `CharacterResponse`

**Эндпоинты:**
```
POST   /api/v1/characters          — создать персонажа
GET    /api/v1/characters/{id}     — получить
PUT    /api/v1/characters/{id}     — обновить (hp, уровень и т.д.)
GET    /api/v1/characters          — список персонажей пользователя
DELETE /api/v1/characters/{id}     — удалить
```

Все требуют `Authorization: Bearer <token>`.

**Поля персонажа:**
- name, race (Human/Elf/Dwarf/Halfling/etc)
- class_name (Fighter/Wizard/Rogue/Cleric/etc)
- stats: str, dex, con, int, wis, cha (3-18)
- hp_max, ac
- equipment (список)
- background (текст)

**Проверка:** создать персонажа → получить → обновить hp → проверить.

---

### Task 2.4: Привязать персонажа к чату

**Objective:** Чат использует персонажа как контекст для AI

**Файлы:**
- Изменить: `rpg_backend/app/models.py` — `ChatRequest` получает опциональный `character_id`
- Изменить: `rpg_backend/app/services/chat_service.py` — если character_id передан, загружать персонажа из БД и добавлять в system prompt
- Изменить: `rpg_backend/app/api/v1/chat.py` — пробрасывать character_id

**Логика:**
```python
async def handle_message(self, request: ChatRequest) -> ChatResponse:
    character = None
    if request.character_id:
        character = await self._load_character(request.character_id)
    history = self._get_history(request.user_id)
    history[0] = {"role": "system", "content": self._build_system_prompt(character)}
    ...
```

**Проверка:** чат с character_id → AI знает имя, класс, статы персонажа.

---

## Этап 3: Умные кубики

### Task 3.1: Добавить dice roll в API модель

**Objective:** Броски кубиков становятся частью диалога

**Файлы:**
- Изменить: `rpg_backend/app/models.py` — добавить `DiceRoll` в тело сообщения или отдельный тип

**Новая модель:**
```python
class ChatRequest(BaseModel):
    user_id: str
    character_id: str | None = None
    message: str = ""
    dice_roll: DiceRoll | None = None  # новый!

class DiceRoll(BaseModel):
    dice: list[int]  # [6, 6, 6] для 3d6
    results: list[int]  # [4, 2, 6]
    modifier: int = 0
    label: str = ""  # "Проверка ловкости" — опционально
```

**Проверка:** POST с dice_roll → в историю добавляется "🎲 Бросок 3d6: [4, 2, 6] + 2 = 14 (Проверка ловкости)".

---

### Task 3.2: Обработка dice_roll в chat_service

**Objective:** AI видит броски в правильном формате

**Файлы:**
- Изменить: `rpg_backend/app/services/chat_service.py`

**Логика:** если в запросе есть `dice_roll`, форматировать его как читаемое сообщение перед отправкой в AI:
```
"🎲 Игрок бросает: 3d6 проверка ловкости [4, 2, 6] + 2 = 14 (против DC 15 — провал)"
```

Функция `_format_dice_message(roll: DiceRoll) -> str`:
- Подсвечивает криты (20 — успех, 1 — провал)
- Показывает сумму + модификатор
- Если есть label — добавляет

**Проверка:** отправить dice_roll с label="Атака мечом" → AI должен описать результат атаки.

---

### Task 3.3: Обновить клиент — multi-dice + модификаторы

**Objective:** Flutter: выбор нескольких кубиков, добавление модификатора

**Файлы:**
- Изменить: `rpg_client/lib/services/dice_service.dart`
- Изменить: `rpg_client/lib/widgets/dice_roller.dart`

**DiceService:**
```dart
static DiceResult rollMultiple(List<int> dice, {int modifier = 0}) {
  final results = dice.map((s) => roll(s)).toList();
  return DiceResult(dice: dice, results: results, modifier: modifier);
}
```

**DiceRoller UI:**
- Выбор нескольких кубиков: тапы "d6" ×3 → бросок 3d6
- Поле для модификатора (+/- N)
- Поле для лейбла ("Атака мечом")
- Кнопка "Бросить всё"

**Проверка:** выбрать 3d6 с модификатором +2 → в чате появляется красивое сообщение о броске.

---

### Task 3.4: Отправлять броски на сервер (AI видит)

**Objective:** Броски не просто показываются локально, а уходят на сервер

**Файлы:**
- Изменить: `rpg_client/lib/providers/chat_provider.dart`
- Изменить: `rpg_client/lib/services/chat_api_service.dart`

**chat_api_service:**
```dart
Future<String> sendDiceRoll({
  required String userId,
  String? characterId,
  required DiceRollRequest roll,
}) async { ... }
```

**chat_provider:**
```dart
Future<void> rollAndSend(List<int> dice, int modifier, String label) async {
  final result = DiceService.rollMultiple(dice, modifier: modifier);
  _addMessage('user', DiceService.formatMultiRoll(result));
  // Отправляем на сервер как часть диалога
  final reply = await api.sendDiceRoll(
    userId: state.userId,
    characterId: state.characterId,
    roll: result.toRequest(label: label),
  );
  _addMessage('assistant', reply, markdown: true);
}
```

**Проверка:** бросить d20 с лейблом "Проверка восприятия" → AI отвечает с учётом результата.

---

### Task 3.5: Tappable дайсы — парсинг AI-подсказок

**Objective:** AI говорит "брось d20 на проверку ловкости" → клиент подсвечивает это как кнопку

**Файлы:**
- Создать: `rpg_client/lib/utils/dice_parser.dart`
- Изменить: `rpg_client/lib/widgets/chat_message_tile.dart`

**dice_parser.dart:**
```dart
// Ищет в тексте паттерны вида "брось d20", "сделай бросок d6", "3d8 урона"
// Возвращает список найденных кубиков для tappable-кнопок
List<ParsedRoll> parseDiceHints(String text);
```

**chat_message_tile:** если в ответе AI найдены дайс-подсказки — рендерить их как кнопки "🎲 d20 (ловкость)", по тапу — сразу бросать и отправлять.

**Проверка:** AI пишет "брось d20 на проверку акробатики" → под сообщением появляется кнопка "🎲 d20 — Акробатика".

---

## Этап 4: Клиент — экраны авторизации и персонажа

### Task 4.1: Экран логина/регистрации

**Objective:** Пользователь может залогиниться или зарегистрироваться

**Файлы:**
- Создать: `rpg_client/lib/screens/auth_screen.dart`
- Создать: `rpg_client/lib/providers/auth_provider.dart`
- Создать: `rpg_client/lib/services/auth_service.dart`

**auth_service.dart:**
```dart
Future<AuthResult> login(String username, String password) async { ... }
Future<AuthResult> register(String username, String password) async { ... }
```

**auth_provider:** хранит токен в shared_preferences, состояние isLoggedIn.

**auth_screen:** две вкладки — вход / регистрация. Тёмная D&D тема, поля username + password.

**Проверка:** зарегистрироваться → токен сохранён → авто-логин при перезапуске.

---

### Task 4.2: Экран создания персонажа

**Objective:** Пошаговое создание персонажа D&D 5e

**Файлы:**
- Создать: `rpg_client/lib/screens/character_create_screen.dart`
- Создать: `rpg_client/lib/providers/character_provider.dart`
- Создать: `rpg_client/lib/services/character_service.dart`

**Шаги создания:**
1. Имя персонажа
2. Раса (выбор из списка: Human, Elf, Dwarf, Halfling, Dragonborn, Tiefling, Half-Orc, Gnome)
3. Класс (Fighter, Wizard, Rogue, Cleric, Ranger, Paladin, Bard, Druid, Barbarian, Warlock, Sorcerer, Monk)
4. Характеристики (point-buy или стандартный массив: 15,14,13,12,10,8)
5. Снаряжение (пресеты по классу) и предыстория

**character_service.dart:**
```dart
Future<Character> createCharacter(String token, CharacterCreate data) async { ... }
Future<List<Character>> getCharacters(String token) async { ... }
Future<Character> updateCharacter(String token, String id, CharacterUpdate data) async { ... }
```

**Проверка:** создать персонажа → отображается в списке → можно выбрать для игры.

---

### Task 4.3: Экран выбора персонажа и интеграция с чатом

**Objective:** Перед чатом игрок выбирает персонажа (или создаёт нового)

**Файлы:**
- Создать: `rpg_client/lib/screens/character_select_screen.dart`
- Изменить: `rpg_client/lib/screens/chat_screen.dart`
- Изменить: `rpg_client/lib/providers/chat_provider.dart`

**Логика:**
1. При запуске → auth_screen (если нет токена) → character_select_screen (если нет активного персонажа) → chat_screen
2. В шапке чата — имя и класс персонажа
3. chat_provider хранит characterId, отправляет его с каждым запросом

**Проверка:** полный флоу — регистрация → создание персонажа → чат с AI, который знает имя и класс.

---

## Этап 5: Сборка и релиз

### Task 5.1: Обновить Dockerfile и перезапустить

**Objective:** Бэкенд с новой функциональностью работает в Docker

**Файлы:**
- Изменить: `rpg_backend/Dockerfile` — добавить aiosqlite, bcrypt, PyJWT
- Изменить: `rpg_backend/docker-compose.yml` — volume для rpg.db

**Проверка:** `docker compose up -d --build` → curl /health → OK.

---

### Task 5.2: Собрать APK v2 и выложить релиз

**Objective:** Новый APK с авторизацией, персонажами, умными кубиками

**Проверка:** APK устанавливается, авторизация работает, AI отвечает с учётом персонажа и правил D&D.

---
