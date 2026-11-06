"""Миграции БД: init_db + все _migrate_* (v1..v33)."""


import aiosqlite
from pathlib import Path
from uuid import uuid4

from app.db.connection import DB_PATH, get_db


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    """True если колонка column уже есть в таблице table."""
    cursor = await db.execute(
        "SELECT 1 FROM pragma_table_info(?) WHERE name = ?", (table, column)
    )
    return await cursor.fetchone() is not None


async def _add_column_if_missing(
    db: aiosqlite.Connection, table: str, column: str, ddl: str
) -> None:
    """ALTER TABLE ... ADD COLUMN, если колонки ещё нет. Ошибки глушатся
    (идемпотентность — таблица может быть пересоздана параллельной миграцией)."""
    try:
        if await _column_exists(db, table, column):
            return
        await db.execute(ddl)
        await db.commit()
    except Exception:
        pass


async def _ensure_table(db: aiosqlite.Connection, table: str, create_sql: str) -> bool:
    """Создать таблицу, только если её ещё нет (SELECT 1 ... LIMIT 0 проба).
    create_sql должен содержать CREATE TABLE IF NOT EXISTS (+ индексы при необходимости).
    Возвращает True если таблица была создана этим вызовом."""
    try:
        await db.execute(f"SELECT 1 FROM {table} LIMIT 0")
        return False
    except Exception:
        await db.execute(create_sql)
        await db.commit()
        return True


async def _migrate_v2_to_v3(db: aiosqlite.Connection) -> None:
    """Добавить колонки modifiers и flavor в таблицу items."""
    for col in ("modifiers", "flavor"):
        default = "'{}'" if col == "modifiers" else "''"
        await _add_column_if_missing(
            db, "items", col,
            f"ALTER TABLE items ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}",
        )


async def _migrate_v4_spells(db: aiosqlite.Connection) -> None:
    """Убедиться что таблица character_spells существует."""
    await _ensure_table(db, "character_spells", _SPELLS_TABLE_SQL)


async def _migrate_v5_multiplayer(db: aiosqlite.Connection) -> None:
    """Добавить таблицы для мультиплеера."""
    await db.executescript(_MULTIPLAYER_SCHEMA)
    await db.commit()

_SPELLS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS character_spells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    spell_key TEXT NOT NULL,
    spell_name TEXT NOT NULL,
    spell_level INTEGER NOT NULL DEFAULT 0,
    school TEXT NOT NULL DEFAULT '',
    "desc" TEXT NOT NULL DEFAULT '',
    casting_time TEXT NOT NULL DEFAULT '',
    "range" TEXT NOT NULL DEFAULT '',
    components TEXT NOT NULL DEFAULT '',
    duration TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_character_spells ON character_spells(character_id);
"""

_MULTIPLAYER_SCHEMA = """
-- Групповые игровые сессии
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    invite_code TEXT UNIQUE NOT NULL,
    state TEXT NOT NULL DEFAULT 'lobby',
    turn_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Участники сессии
CREATE TABLE IF NOT EXISTS session_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    character_id TEXT,
    role TEXT NOT NULL DEFAULT 'player',
    initiative INTEGER,
    turn_order INTEGER NOT NULL DEFAULT 0,
    is_ready INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL,
    UNIQUE(session_id, user_id)
);

-- Сообщения групповой игры
CREATE TABLE IF NOT EXISTS game_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    character_id TEXT,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    dice_roll TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_members_session ON session_members(session_id);
CREATE INDEX IF NOT EXISTS idx_session_members_user ON session_members(user_id);
CREATE INDEX IF NOT EXISTS idx_game_messages_session ON game_messages(session_id, created_at);
"""

# ── Одноколоночные ALTER-миграции: (версия-функция ниже, таблица, колонка, DDL) ──

_ADD_COLUMN_MIGRATIONS = [
    ("game_sessions", "current_turn_user_id",
     "ALTER TABLE game_sessions ADD COLUMN current_turn_user_id TEXT"),
    ("characters", "subclass",
     "ALTER TABLE characters ADD COLUMN subclass TEXT NOT NULL DEFAULT ''"),
    ("characters", "mixed_heritage",
     "ALTER TABLE characters ADD COLUMN mixed_heritage TEXT NOT NULL DEFAULT '{}'"),
    ("characters", "xp",
     "ALTER TABLE characters ADD COLUMN xp INTEGER NOT NULL DEFAULT 0"),
    ("characters", "subrace",
     "ALTER TABLE characters ADD COLUMN subrace TEXT NOT NULL DEFAULT ''"),
    ("characters", "is_dead",
     "ALTER TABLE characters ADD COLUMN is_dead INTEGER NOT NULL DEFAULT 0"),
    ("characters", "karma",
     "ALTER TABLE characters ADD COLUMN karma INTEGER NOT NULL DEFAULT 0"),
]


def _make_add_column_migrator(doc: str, table: str, column: str, ddl: str):
    async def _migrate(db: aiosqlite.Connection) -> None:
        """%(doc)s"""
        await _add_column_if_missing(db, table, column, ddl)
    _migrate.__doc__ = doc
    _migrate.__name__ = f"_migrate_{table}_{column}"
    return _migrate


_migrate_v6_session_turn = _make_add_column_migrator(
    "Добавить колонку current_turn_user_id если её нет.",
    *_ADD_COLUMN_MIGRATIONS[0])
_migrate_v7_subclass = _make_add_column_migrator(
    "Добавить колонку subclass в таблицу characters.",
    *_ADD_COLUMN_MIGRATIONS[1])
_migrate_v8_mixed_heritage = _make_add_column_migrator(
    "Добавить колонку mixed_heritage в таблицу characters.",
    *_ADD_COLUMN_MIGRATIONS[2])
_migrate_v10_xp = _make_add_column_migrator(
    "Добавить колонку xp в таблицу characters.",
    *_ADD_COLUMN_MIGRATIONS[3])
_migrate_v11_subrace = _make_add_column_migrator(
    "Добавить колонку subrace в таблицу characters.",
    *_ADD_COLUMN_MIGRATIONS[4])
_migrate_v13_is_dead = _make_add_column_migrator(
    "Добавить колонку is_dead в characters.",
    *_ADD_COLUMN_MIGRATIONS[5])
_migrate_v30_karma = _make_add_column_migrator(
    "Карма/репутация персонажа — колонка karma в characters.",
    *_ADD_COLUMN_MIGRATIONS[6])

# ── Табличные миграции «создай, если нет» ──

_CHARACTER_CLASSES_SQL = """CREATE TABLE IF NOT EXISTS character_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            class_name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            hit_die INTEGER NOT NULL DEFAULT 8,
            subclass TEXT NOT NULL DEFAULT '',
            features TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(character_id, class_name)
        )"""

_SESSION_MEMORY_SQL = """
            CREATE TABLE IF NOT EXISTS session_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
                block_number INTEGER NOT NULL,
                summary TEXT NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0,
                first_message_id INTEGER,
                last_message_id INTEGER,
                key_npcs TEXT NOT NULL DEFAULT '[]',
                key_items TEXT NOT NULL DEFAULT '[]',
                key_locations TEXT NOT NULL DEFAULT '[]',
                key_quests TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""


async def _migrate_v9_character_classes(db: aiosqlite.Connection) -> None:
    """Добавить таблицу character_classes для мультикласса."""
    if not await _ensure_table(db, "character_classes", _CHARACTER_CLASSES_SQL):
        return
    await db.execute("CREATE INDEX IF NOT EXISTS idx_character_classes ON character_classes(character_id)")
    await db.commit()


async def _migrate_v12_memory_palace(db: aiosqlite.Connection) -> None:
    """Добавить таблицы session_memory и user_memory для мем-паласа."""
    if not await _ensure_table(db, "session_memory", _SESSION_MEMORY_SQL):
        return
    await db.execute("CREATE INDEX IF NOT EXISTS idx_session_memory ON session_memory(session_id, block_number)")

    await _ensure_table(db, "user_memory", """
            CREATE TABLE IF NOT EXISTS user_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                character_id TEXT,
                block_number INTEGER NOT NULL,
                summary TEXT NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0,
                first_message_id INTEGER,
                last_message_id INTEGER,
                key_npcs TEXT NOT NULL DEFAULT '[]',
                key_items TEXT NOT NULL DEFAULT '[]',
                key_locations TEXT NOT NULL DEFAULT '[]',
                key_quests TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_memory ON user_memory(user_id, character_id, block_number)")
    await db.commit()


async def _migrate_v14_game_state(db: aiosqlite.Connection) -> None:
    """Добавить таблицу game_state для persisted state (анти-дрифт)."""
    if not await _ensure_table(db, "game_state", """
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                character_id TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                scene TEXT NOT NULL DEFAULT '',
                weapon TEXT NOT NULL DEFAULT '',
                phase TEXT NOT NULL DEFAULT 'exploration',
                last_reply TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, character_id)
            )
        """):
        return
    await db.execute("CREATE INDEX IF NOT EXISTS idx_game_state_user ON game_state(user_id, character_id)")
    await db.commit()


async def _migrate_v15_drop_game_state_fk(db: aiosqlite.Connection) -> None:
    """Убрать FK на character_id в game_state — мешает characterless-сессиям."""
    cursor = await db.execute("SELECT 1 FROM pragma_foreign_key_list('game_state') WHERE \"from\"='character_id'")
    if await cursor.fetchone():
        await db.execute("PRAGMA foreign_keys = OFF")
        await db.execute("BEGIN IMMEDIATE")
        await db.execute("""
            CREATE TABLE game_state_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                character_id TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                scene TEXT NOT NULL DEFAULT '',
                weapon TEXT NOT NULL DEFAULT '',
                phase TEXT NOT NULL DEFAULT 'exploration',
                last_reply TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, character_id)
            )
        """)
        await db.execute("INSERT INTO game_state_new SELECT * FROM game_state")
        await db.execute("DROP TABLE game_state")
        await db.execute("ALTER TABLE game_state_new RENAME TO game_state")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_game_state_user ON game_state(user_id, character_id)")
        await db.execute("COMMIT")
        await db.execute("PRAGMA foreign_keys = ON")
        await db.commit()


async def _add_columns_if_missing(
    db: aiosqlite.Connection, table: str, columns: list[tuple[str, str]]
) -> None:
    """Для каждой (колонка, default-SQL-литерал): добавить, если нет. Ошибки глушатся."""
    for col, default in columns:
        await _add_column_if_missing(
            db, table, col,
            f"ALTER TABLE {table} ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}",
        )


async def _migrate_v16_boosty(db: aiosqlite.Connection) -> None:
    """Boosty-интеграция: колонки в users + access_codes."""
    # Колонки в users
    await _add_columns_if_missing(db, "users", [
        ("boosty_login", "''"),
        ("subscription_tier", "''"),
        ("subscription_expires", "''"),
        ("is_active", "1"),
    ])

    # Индекс на boosty_login
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_boosty ON users(boosty_login)")
    except Exception:
        pass

    # Таблица access_codes
    if await _ensure_table(db, "access_codes", """
            CREATE TABLE IF NOT EXISTS access_codes (
                code TEXT PRIMARY KEY,
                created_by TEXT NOT NULL DEFAULT '',
                duration_days INTEGER NOT NULL DEFAULT 7,
                used_by TEXT,
                used_at TEXT,
                max_uses INTEGER NOT NULL DEFAULT 1,
                use_count INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """):
        await db.execute("CREATE INDEX IF NOT EXISTS idx_access_codes_used_by ON access_codes(used_by)")


async def _migrate_v17_is_active_int(db: aiosqlite.Connection) -> None:
    """v16 создала is_active как TEXT — исправляем на INTEGER."""
    await db.execute(
        "UPDATE users SET is_active = CAST(is_active AS INTEGER)"
    )
    await db.commit()


async def _migrate_v18_multiverse(db: aiosqlite.Connection) -> None:
    """Мультивселенная: current_world + nsfw_last_styles в game_state."""
    await _add_columns_if_missing(db, "game_state", [
        ("current_world", "'forgotten_realms'"),
        ("nsfw_last_styles", "'[]'"),
        ("nsfw_level", "'on'"),
    ])


async def _migrate_v19_boosty_unique(db: aiosqlite.Connection) -> None:
    """UNIQUE partial index на boosty_login, с предварительной очисткой дубликатов."""
    # 1. Найти и очистить дубликаты
    rows = await db.execute(
        "SELECT boosty_login, COUNT(*) as cnt FROM users "
        "WHERE boosty_login != '' GROUP BY boosty_login HAVING cnt > 1"
    )
    # Материализовать до цикла — вложенные запросы на том же соединении
    # инвалидируют внешний курсор в sqlite
    rows_materialized = await rows.fetchall()
    for row in rows_materialized:
        dupes = await db.execute(
            "SELECT id FROM users WHERE boosty_login = ? "
            "ORDER BY rowid LIMIT -1 OFFSET 1",
            (row["boosty_login"],),
        )
        # Материализуем И внутренний курсор — UPDATE внутри async for
        # может инвалидировать его (тот же класс, что внешний)
        dupes_materialized = await dupes.fetchall()
        for dupe in dupes_materialized:
            await db.execute(
                "UPDATE users SET boosty_login = '', is_active = 0 WHERE id = ?",
                (dupe["id"],),
            )
    await db.commit()

    # 2. Создать индекс
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_boosty_unique "
        "ON users(boosty_login) WHERE boosty_login != ''"
    )
    await db.commit()


async def _migrate_v20_fix_active_default(db: aiosqlite.Connection) -> None:
    """v16 создала is_active с DEFAULT 1 — деактивируем халявщиков. Идемпотентна."""
    # Гард: не перезаписывать уже проставленные значения при каждом перезапуске
    cur = await db.execute(
        "SELECT 1 FROM users WHERE is_active = 1 AND subscription_tier != '' "
        "AND subscription_expires != '' LIMIT 1"
    )
    if await cur.fetchone():
        return  # уже бегала — у пользователей есть корректные подписки

    # Деактивируем всех у кого нет подписки и нет активного кода доступа
    await db.execute(
        "UPDATE users SET is_active = 0 "
        "WHERE (subscription_tier = '' OR subscription_tier IS NULL) "
        "AND (subscription_expires = '' OR subscription_expires IS NULL "
        "     OR datetime(subscription_expires) < datetime('now'))"
    )
    await db.commit()


async def _migrate_v21_payments(db: aiosqlite.Connection) -> None:
    """Добавить таблицу payments для YooKassa."""
    if await _ensure_table(db, "payments", """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                amount_rub INTEGER NOT NULL,
                days INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """):
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        await db.commit()


async def _migrate_v1_to_v2(db: aiosqlite.Connection) -> None:
    """Перенос equipment из JSON-строки в таблицу items."""
    try:
        # Проверим есть ли старая колонка
        if not await _column_exists(db, "characters", "equipment"):
            return
        rows = await db.execute("SELECT id, equipment FROM characters WHERE equipment != '' AND equipment != '[]'")
        old_equip = await rows.fetchall()
        import json
        for row in old_equip:
            try:
                items = json.loads(row["equipment"])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            await db.execute(
                                "INSERT OR IGNORE INTO items (character_id, item_key, item_name, qty, slot, equipped) VALUES (?, ?, ?, 1, 'inventory', 0)",
                                (row["id"], item, item,)
                            )
            except (json.JSONDecodeError, TypeError):
                pass

        # Удаляем старую колонку (SQLite не умеет DROP COLUMN легко, просто оставляем)

        await db.commit()
    except Exception:
        pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    boosty_login TEXT NOT NULL DEFAULT '',
    subscription_tier TEXT NOT NULL DEFAULT '',
    subscription_expires TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    race TEXT NOT NULL,
    class_name TEXT NOT NULL,
    background_name TEXT NOT NULL DEFAULT '',
    subclass TEXT NOT NULL DEFAULT '',
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    stats TEXT NOT NULL DEFAULT '{}',
    hp_max INTEGER NOT NULL,
    hp_current INTEGER NOT NULL,
    ac INTEGER NOT NULL DEFAULT 10,
    init_ac INTEGER NOT NULL DEFAULT 10,
    speed INTEGER NOT NULL DEFAULT 30,
    backstory TEXT NOT NULL DEFAULT '',
    features TEXT NOT NULL DEFAULT '[]',
    proficiencies TEXT NOT NULL DEFAULT '{}',
    skill_proficiencies TEXT NOT NULL DEFAULT '[]',
    languages TEXT NOT NULL DEFAULT '[]',
    mixed_heritage TEXT NOT NULL DEFAULT '{}',
    subrace TEXT NOT NULL DEFAULT '',
    is_dead INTEGER NOT NULL DEFAULT 0,
    gold INTEGER NOT NULL DEFAULT 0,
    appearance TEXT NOT NULL DEFAULT '',
    appearance_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    item_name TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'gear',
    item_subtype TEXT NOT NULL DEFAULT '',
    qty INTEGER NOT NULL DEFAULT 1,
    slot TEXT NOT NULL DEFAULT 'inventory',
    equipped INTEGER NOT NULL DEFAULT 0,
    attunement INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    modifiers TEXT NOT NULL DEFAULT '{}',
    flavor TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
CREATE INDEX IF NOT EXISTS idx_items_character_id ON items(character_id);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    character_id TEXT,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS character_spells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    spell_key TEXT NOT NULL,
    spell_name TEXT NOT NULL,
    spell_level INTEGER NOT NULL DEFAULT 0,
    school TEXT NOT NULL DEFAULT '',
    "desc" TEXT NOT NULL DEFAULT '',
    casting_time TEXT NOT NULL DEFAULT '',
    "range" TEXT NOT NULL DEFAULT '',
    components TEXT NOT NULL DEFAULT '',
    duration TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_char ON chat_history(user_id, character_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_character_spells ON character_spells(character_id);

-- ========================
-- MULTIPLAYER v2.0
-- ========================

CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invite_code TEXT UNIQUE NOT NULL,
    state TEXT NOT NULL DEFAULT 'lobby' CHECK(state IN ('lobby','playing','finished')),
    turn_index INTEGER NOT NULL DEFAULT 0,
    current_turn_user_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS session_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id TEXT REFERENCES characters(id) ON DELETE SET NULL,
    role TEXT NOT NULL DEFAULT 'player' CHECK(role IN ('owner','player')),
    initiative INTEGER,
    turn_order INTEGER NOT NULL DEFAULT 0,
    is_ready INTEGER NOT NULL DEFAULT 0,
    UNIQUE(session_id, user_id)
);

CREATE TABLE IF NOT EXISTS group_chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    character_id TEXT,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    dice_roll TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(from_user_id, to_user_id)
);

CREATE INDEX IF NOT EXISTS idx_game_sessions_owner ON game_sessions(owner_id);
CREATE INDEX IF NOT EXISTS idx_session_members_session ON session_members(session_id);
CREATE INDEX IF NOT EXISTS idx_session_members_user ON session_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_chat_session ON group_chat_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_friend_requests_from ON friend_requests(from_user_id, status);
CREATE INDEX IF NOT EXISTS idx_friend_requests_to ON friend_requests(to_user_id, status);

-- ========================
-- MEMORY PALACE v1.0
-- ========================

CREATE TABLE IF NOT EXISTS session_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    block_number INTEGER NOT NULL,
    summary TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    first_message_id INTEGER,
    last_message_id INTEGER,
    key_npcs TEXT NOT NULL DEFAULT '[]',
    key_items TEXT NOT NULL DEFAULT '[]',
    key_locations TEXT NOT NULL DEFAULT '[]',
    key_quests TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_session_memory ON session_memory(session_id, block_number);

CREATE TABLE IF NOT EXISTS user_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id TEXT,
    block_number INTEGER NOT NULL,
    summary TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    first_message_id INTEGER,
    last_message_id INTEGER,
    key_npcs TEXT NOT NULL DEFAULT '[]',
    key_items TEXT NOT NULL DEFAULT '[]',
    key_locations TEXT NOT NULL DEFAULT '[]',
    key_quests TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_user_memory ON user_memory(user_id, character_id, block_number);

-- ========================
-- PERSISTED GAME STATE (anti-drift)
-- ========================

CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    scene TEXT NOT NULL DEFAULT '',
    weapon TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT 'exploration',
    last_reply TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, character_id)
);

CREATE INDEX IF NOT EXISTS idx_game_state_user ON game_state(user_id, character_id);

CREATE TABLE IF NOT EXISTS access_codes (
    code TEXT PRIMARY KEY,
    created_by TEXT NOT NULL DEFAULT '',
    duration_days INTEGER NOT NULL DEFAULT 7,
    used_by TEXT,
    used_at TEXT,
    max_uses INTEGER NOT NULL DEFAULT 1,
    use_count INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_access_codes_used_by ON access_codes(used_by);
"""


async def _migrate_v22_quests(db: aiosqlite.Connection) -> None:
    """Добавить таблицу quests для журнала квестов."""
    try:
        await db.execute("SELECT 1 FROM quests LIMIT 0")
    except Exception:
        await db.executescript("""
CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    quest_key TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','failed')),
    objectives TEXT NOT NULL DEFAULT '[]',
    rewards TEXT NOT NULL DEFAULT '{}',
    source_npc TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_quests_character ON quests(character_id);
""")
        await db.commit()


async def _migrate_v23_guest_purchases(db: aiosqlite.Connection) -> None:
    """Добавить таблицу guest_purchases для хранения кодов гостевых покупок."""
    try:
        await db.execute("SELECT 1 FROM guest_purchases LIMIT 0")
    except Exception:
        await db.executescript("""
CREATE TABLE IF NOT EXISTS guest_purchases (
    payment_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','awaiting_registration')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_guest_purchases_username ON guest_purchases(username);
""")
    await db.commit()


async def _migrate_v24_fix_guest_status(db: aiosqlite.Connection) -> None:
    """Расширить CHECK guest_purchases.status — добавить 'awaiting_registration'."""
    try:
        await db.execute("SELECT 1 FROM guest_purchases LIMIT 0")
    except Exception:
        return

    cur = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='guest_purchases'"
    )
    row = await cur.fetchone()
    if row and "awaiting_registration" in (row[0] or ""):
        return

    await db.executescript("""
CREATE TABLE guest_purchases_new (
    payment_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','awaiting_registration')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
INSERT INTO guest_purchases_new SELECT * FROM guest_purchases;
DROP TABLE guest_purchases;
ALTER TABLE guest_purchases_new RENAME TO guest_purchases;
CREATE INDEX IF NOT EXISTS idx_guest_purchases_username ON guest_purchases(username);
""")
    await db.commit()


async def _migrate_v25_appearance(db: aiosqlite.Connection) -> None:
    """Добавить колонки appearance и appearance_url в таблицу characters (внешность персонажа)."""
    try:
        await db.execute("SELECT 1 FROM characters LIMIT 0")
    except Exception:
        return

    for col, ddl in (
        ("appearance", "ALTER TABLE characters ADD COLUMN appearance TEXT NOT NULL DEFAULT ''"),
        ("appearance_url", "ALTER TABLE characters ADD COLUMN appearance_url TEXT NOT NULL DEFAULT ''"),
    ):
        if await _column_exists(db, "characters", col):
            continue
        await db.execute(ddl)
    await db.commit()
async def _migrate_v26_npc_appearance(db: aiosqlite.Connection) -> None:
    """Таблица внешности NPC — привязка картинки к конкретному NPC (по имени),
    с той же логикой изменений, что у персонажа."""
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS npc_appearance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            npc_name TEXT NOT NULL DEFAULT '',
            appearance TEXT NOT NULL DEFAULT '',
            appearance_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(character_id, npc_name)
        )
        """
    )
    await db.commit()


async def _migrate_v27_npc_state(db: aiosqlite.Connection) -> None:
    """Реестр NPC с состоянием (жив/мёртв, локация, отношение).

    Чинит баг «убитая бабка воскресает»: раньше NPC жили только в
    npc_appearance (кто получил картинку) и в key_npcs саммари (роль,
    не сущность). История режется до max_history → модель забывала
    убийство и генерировала NPC заново с другим поведением.

    Теперь каждый NPC — строка в БД с alive/attitude/location.
    Промпт подгружает список с состоянием: «Агата — МЁРТВА (убита тобой)»,
    модель не может воскресить мёртвого.
    """
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            npc_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            alive INTEGER NOT NULL DEFAULT 1,
            attitude TEXT NOT NULL DEFAULT 'neutral',
            description TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(character_id, npc_name)
        )
        """
    )
    # Индекс на живых NPC для быстрой выборки по локации
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_npcs_char_alive ON npcs(character_id, alive)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_npcs_location ON npcs(character_id, location, alive)"
    )
async def _migrate_v28_prompt_log(db: aiosqlite.Connection) -> None:
    """Промпт-аудит: что реально подгружается в system prompt каждого запроса.
    Позволяет увидеть, какие секции попадают в промпт, их размер, сколько
    истории и NPC — для диагностики «почему модель забыла X»."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS prompt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            system_len INTEGER DEFAULT 0,
            history_msgs INTEGER DEFAULT 0,
            history_chars INTEGER DEFAULT 0,
            sections TEXT DEFAULT '{}',
            npc_registry_count INTEGER DEFAULT 0,
            npc_known_count INTEGER DEFAULT 0,
            full_system TEXT DEFAULT ''
        )"""
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_prompt_log_char ON prompt_log(character_id, created_at)"
    )


async def _migrate_v29_quests(db: aiosqlite.Connection) -> None:
    """Квестовый журнал: активные квесты персонажа, видимые DM и игроку."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            location TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )"""
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_quests_char ON quests(character_id, status)"
    )


async def _migrate_v31_companions(db: aiosqlite.Connection) -> None:
    """Спутники-компаньоны: существа/соратники, путешествующие с персонажем."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS companions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            name TEXT NOT NULL,
            species TEXT DEFAULT '',
            description TEXT DEFAULT '',
            mood TEXT DEFAULT 'нейтральное',
            status TEXT DEFAULT 'active',
            location TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )"""
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_companions_char ON companions(character_id, status)"
    )


async def _import_legacy_scene_index(db: aiosqlite.Connection) -> None:
    """Миграция старого index.json сцен → image_assets (best-effort).

    Старый index не удаляем — это бэкап; новые записи идут в БД.
    """
    try:
        idx_path = Path(__file__).parent.parent / "data" / "scenes" / "index.json"
        if not idx_path.is_file():
            return
        import json as _json

        old = _json.loads(idx_path.read_text())
        if not isinstance(old, list):
            return
        for entry in old:
            if not isinstance(entry, dict) or not entry.get("url"):
                continue
            url = str(entry["url"])
            # Уже импортирован?
            cur = await db.execute("SELECT 1 FROM image_assets WHERE url = ? AND kind = 'scene' LIMIT 1", (url,))
            if await cur.fetchone():
                continue
            await db.execute(
                """INSERT OR IGNORE INTO image_assets
                   (id, kind, location_key, npc_name, character_id, meta, tags, url, file_name, use_count, last_used_at, created_at)
                   VALUES (?, 'scene', ?, '', ?, '{}', ?, ?, ?, 1, ?, ?)""",
                (
                    str(uuid4()),
                    str(entry.get("location_key") or ""),
                    str(entry.get("character_id") or ""),
                    _json.dumps(entry.get("tags") or [], ensure_ascii=False),
                    url,
                    url.rsplit("/", 1)[-1],
                    entry.get("created_at") or "",
                    entry.get("created_at") or "",
                ),
            )
        await db.commit()
    except Exception:
        pass


async def _migrate_v32_image_assets(db: aiosqlite.Connection) -> None:
    """Единая база сгенерированных картинок (сцены, NPC, портреты персонажей).

    Картинки привязаны к ИГРОВОМУ контенту (локация/NPC), а не к игроку:
    - kind='scene' → location_key (слаг локации) + tags;
    - kind='npc' → npc_name + meta (раса/роль/внешность);
    - kind='character' → character_id + meta (раса/класс/внешность).

    image_views — кто какую картинку уже видел (для индивидуальности:
    игрок не получает ту же картинку NPC/локации в новой игре).
    """
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS image_assets (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,                    -- scene | npc | character
            location_key TEXT NOT NULL DEFAULT '', -- слаг локации (для scene)
            npc_name TEXT NOT NULL DEFAULT '',     -- имя NPC (для npc)
            character_id TEXT NOT NULL DEFAULT '', -- владелец (для character)
            meta TEXT NOT NULL DEFAULT '{}',       -- JSON: раса, роль, внешность, класс
            tags TEXT NOT NULL DEFAULT '[]',       -- JSON: теги для поиска (для scene)
            url TEXT NOT NULL DEFAULT '',          -- URL для отдачи клиенту
            file_name TEXT NOT NULL DEFAULT '',    -- файл на диске
            use_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_assets_kind ON image_assets(kind);
        CREATE INDEX IF NOT EXISTS idx_assets_loc ON image_assets(kind, location_key);
        CREATE INDEX IF NOT EXISTS idx_assets_npc ON image_assets(kind, npc_name);
        CREATE INDEX IF NOT EXISTS idx_assets_char ON image_assets(kind, character_id);

        CREATE TABLE IF NOT EXISTS image_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL REFERENCES image_assets(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL DEFAULT '',
            viewed_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(asset_id, user_id, character_id)
        );
        CREATE INDEX IF NOT EXISTS idx_views_user ON image_views(user_id);
        """
    )
    await db.commit()

    # Миграция старого index.json сцен → image_assets
    await _import_legacy_scene_index(db)
    await db.commit()


async def _migrate_v33_combat_map(db: aiosqlite.Connection) -> None:
    """Бой (инициатива/раунды) + открытые локации карты мира."""
    for col, default in [
        ("combat", "'{}'"),          # JSON: {"order": [...], "round": N, "started": "..."}
        ("discovered_locations", "'[]'"),  # JSON: ["врата балдура", ...]
    ]:
        try:
            cursor = await db.execute(
                f"SELECT 1 FROM pragma_table_info('game_state') WHERE name='{col}'"
            )
            if not await cursor.fetchone():
                await db.execute(
                    f"ALTER TABLE game_state ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}"
                )
        except Exception:
            pass
    await db.commit()


async def init_db() -> None:
    """Создать таблицы, если их нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        await db.executescript(_SCHEMA)
        await db.commit()
        # Миграция старых данных
        await _migrate_v1_to_v2(db)
        await _migrate_v2_to_v3(db)
        await _migrate_v4_spells(db)
        await _migrate_v5_multiplayer(db)
        await _migrate_v6_session_turn(db)
        await _migrate_v7_subclass(db)
        await _migrate_v8_mixed_heritage(db)
        await _migrate_v9_character_classes(db)
        await _migrate_v10_xp(db)
        await _migrate_v11_subrace(db)
        await _migrate_v12_memory_palace(db)
        await _migrate_v13_is_dead(db)
        await _migrate_v14_game_state(db)
        await _migrate_v15_drop_game_state_fk(db)
        await _migrate_v16_boosty(db)
        await _migrate_v17_is_active_int(db)
        await _migrate_v18_multiverse(db)
        await _migrate_v19_boosty_unique(db)
        await _migrate_v20_fix_active_default(db)
        await _migrate_v21_payments(db)
        await _migrate_v22_quests(db)
        await _migrate_v23_guest_purchases(db)
        await _migrate_v24_fix_guest_status(db)
        await _migrate_v25_appearance(db)
        await _migrate_v26_npc_appearance(db)
        await _migrate_v27_npc_state(db)
        await _migrate_v28_prompt_log(db)
        await _migrate_v29_quests(db)
        await _migrate_v30_karma(db)
        await _migrate_v31_companions(db)
        await _migrate_v32_image_assets(db)
        await _migrate_v33_combat_map(db)
    finally:
        await db.close()
