"""Тесты полного воркфлоу: создание персонажа, инвентарь, слоты, AI-ревью."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth import create_token
from conftest import auth_headers as _auth_header

client = TestClient(app)


# ──────────────────────────────────────────────
# STEP 1: create (раса + класс)
# ──────────────────────────────────────────────

def test_create_character_returns_race_class_info():
    r = client.post("/api/v1/characters/create", json={
        "name": "Гэндальф",
        "race": "Человек",
        "class_name": "Волшебник",
    }, headers=_auth_header())
    assert r.status_code == 201
    data = r.json()
    assert "racial_traits" in data
    assert "class_features" in data
    assert "skill_choices" in data
    assert data["race"] == "Человек"
    assert data["class_name"] == "Волшебник"


def test_create_character_unknown_race():
    r = client.post("/api/v1/characters/create", json={
        "name": "X",
        "race": "Марсианин",
        "class_name": "Воин",
    }, headers=_auth_header())
    assert r.status_code == 400


def test_create_character_unknown_class():
    r = client.post("/api/v1/characters/create", json={
        "name": "X",
        "race": "Человек",
        "class_name": "Бухгалтер",
    }, headers=_auth_header())
    assert r.status_code == 400


# ──────────────────────────────────────────────
# SRD endpoints
# ──────────────────────────────────────────────

def test_srd_backgrounds():
    r = client.get("/api/v1/srd/backgrounds")
    assert r.status_code == 200
    assert len(r.json()["backgrounds"]) >= 8


def test_srd_classes():
    r = client.get("/api/v1/srd/classes")
    assert r.status_code == 200
    classes = r.json()["classes"]
    assert any(c["name"] == "Волшебник" for c in classes)
    assert any(c["name"] == "Воин" for c in classes)


def test_srd_races():
    r = client.get("/api/v1/srd/races")
    assert r.status_code == 200
    assert len(r.json()["races"]) >= 7


def test_srd_equipment():
    r = client.get("/api/v1/srd/equipment")
    assert r.status_code == 200
    eq = r.json()["equipment"]
    assert "weapon" in eq
    assert "armor" in eq


# ──────────────────────────────────────────────
# Полный воркфлоу создания персонажа
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_character_creation_workflow():
    """
    Эмулируем что делает клиент:
    1. POST /characters/create → получаем опции
    2. POST /characters/{id}/attributes → сначала надо создать черновик через create, 
       но create только возвращает данные. Надо сначала создать запись.
    
    Упрощённо: тестируем ручной create через низкоуровневый доступ.
    """
    import aiosqlite
    from app.auth import new_id
    from app.db import DB_PATH, init_db

    await init_db()

    user_id = "wf-user-1"
    char_id = new_id()

    # Вставляем черновик персонажа напрямую
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")

    # Создаём пользователя
    await db.execute(
        "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (user_id, "wfuser", "hash"),
    )
    await db.execute(
        """INSERT INTO characters (id, user_id, name, race, class_name, level, stats, hp_max, hp_current, ac, init_ac)
           VALUES (?, ?, ?, ?, ?, 1, '{}', 8, 8, 10, 10)""",
        (char_id, user_id, "Тестовый", "Человек", "Воин"),
    )
    await db.commit()
    await db.close()

    # Шаг 2: ставим статы
    token = create_token(user_id)
    r = client.post(f"/api/v1/characters/{char_id}/stats", json={
        "stats": {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8},
        "skill_proficiencies": ["athletics", "perception"],
        "languages": ["общий", "дварфийский"],
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["stats"]["str"] == 16

    # Шаг 3: финализируем с предысторией
    with patch("app.api.v1.characters.creation._ai_review_backstory", new=AsyncMock(return_value="Отличная история!")):
        r = client.post(
            f"/api/v1/characters/{char_id}/finalize",
            params={"background_name": "Солдат"},
            json={"backstory": "Был стражником в городской страже. Потерял напарника в бою с гоблинами и поклялся защищать невинных."},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    result = r.json()
    assert result["character"]["name"] == "Тестовый"
    assert result["character"]["class_name"] == "Воин"
    assert result["character"]["backstory"]
    assert len(result["starting_items"]) > 0
    assert len(result["features"]) > 0
    assert result["dm_notes"] == "Отличная история!"


# ──────────────────────────────────────────────
# Инвентарь
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_item():
    import aiosqlite
    from app.auth import new_id
    from app.db import DB_PATH, init_db

    await init_db()
    user_id = "inv-user-1"
    char_id = new_id()
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)", (user_id, "invuser", "hash"))
    await db.execute(
        "INSERT INTO characters (id, user_id, name, race, class_name, level, stats, hp_max, hp_current, ac, init_ac) VALUES (?, ?, ?, ?, ?, 1, '{}', 10, 10, 10, 10)",
        (char_id, user_id, "Инвентарный", "Человек", "Воин"),
    )
    await db.commit()
    await db.close()

    token = create_token(user_id)
    # Добавляем предмет
    r = client.post(f"/api/v1/characters/{char_id}/items", json={
        "item_key": "longsword",
        "qty": 1,
        "slot": "main_hand",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    item = r.json()
    assert item["item_name"] == "Длинный меч"
    assert item["item_type"] == "weapon"
    item_id = item["id"]

    # Список предметов
    r = client.get(f"/api/v1/characters/{char_id}/items", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Удаляем
    r = client.delete(f"/api/v1/characters/{char_id}/items/{item_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204

    r = client.get(f"/api/v1/characters/{char_id}/items", headers={"Authorization": f"Bearer {token}"})
    assert len(r.json()) == 0


# ──────────────────────────────────────────────
# AC calculation
# ──────────────────────────────────────────────

def test_ac_with_leather_armor():
    from app.api.v1.character_helpers import _compute_ac
    items = [
        {"item_key": "leather_armor", "equipped": True, "slot": "body"},
    ]
    stats = {"dex": 16}  # +3
    # leather: 11 + DEX
    assert _compute_ac(stats, items, "Воин") == 14


def test_ac_with_chain_mail_and_shield():
    from app.api.v1.character_helpers import _compute_ac
    items = [
        {"item_key": "chain_mail", "equipped": True, "slot": "body"},
        {"item_key": "shield", "equipped": True, "slot": "off_hand"},
    ]
    stats = {"dex": 12}
    # chain mail: 16 (no DEX) + shield: 2 = 18
    assert _compute_ac(stats, items, "Воин") == 18


def test_ac_barbarian_unarmored():
    from app.api.v1.character_helpers import _compute_ac
    stats = {"dex": 14, "con": 16}  # +2 DEX, +3 CON
    # barbarian unarmored: 10 + DEX + CON = 15
    assert _compute_ac(stats, [], "Варвар") == 15


def test_ac_monk_unarmored():
    from app.api.v1.character_helpers import _compute_ac
    stats = {"dex": 16, "wis": 14}  # +3 DEX, +2 WIS
    # monk unarmored: 10 + DEX + WIS = 15
    assert _compute_ac(stats, [], "Монах") == 15


# ──────────────────────────────────────────────
# format_character_for_prompt
# ──────────────────────────────────────────────

def test_format_character_with_items():
    from app.knowledge.srd_rules import format_character_for_prompt
    char = {
        "name": "Тест",
        "race": "Человек",
        "class_name": "Воин",
        "level": 1,
        "stats": {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8},
        "hp_max": 12,
        "hp_current": 12,
        "ac": 18,
        "speed": 30,
        "skill_proficiencies": ["athletics", "perception"],
        "languages": ["общий", "дварфийский"],
        "features": [{"name": "Второе дыхание", "desc": "..."}],
        "items": [
            {"item_name": "Кольчуга", "equipped": True, "slot": "body"},
            {"item_name": "Длинный меч", "equipped": True, "slot": "main_hand"},
            {"item_name": "Щит", "equipped": True, "slot": "off_hand"},
            {"item_name": "Факел", "equipped": False, "slot": "inventory"},
        ],
        "backstory": "Старый солдат.",
    }
    result = format_character_for_prompt(char)
    assert "СИЛ 16 (+3)" in result
    assert "КД**: 18" in result
    assert "Кольчуга" in result
    assert "Второе дыхание" in result
    # Неэкипированное попадает в «рюкзак», а не в активные слоты
    assert "Факел" in result
    assert "рюкзаке" in result.lower()


def test_dm_notes_parsing_stats():
    from app.api.v1.character_helpers import _parse_dm_changes
    notes = "Твой персонаж явно силён. Предлагаю СИЛ = 16 и ЛОВ = 12. [ITEM: smith_hammer] [FEAT: Кузнечное дело]"
    stats, items, feats = _parse_dm_changes(notes, {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
    assert stats["str"] == 16
    assert stats["dex"] == 12
    assert len(items) == 1
    assert items[0]["item_key"] == "smith_hammer"
    assert len(feats) == 1
    assert feats[0]["name"] == "Кузнечное дело"