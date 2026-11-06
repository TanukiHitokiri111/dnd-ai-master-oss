from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.models import ChatResponse
from conftest import auth_headers, register_user

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_chat_validation_empty_message():
    r = client.post("/api/v1/chat", json={"user_id": "u1", "message": ""})
    assert r.status_code == 422


def test_chat_validation_missing_fields():
    r = client.post("/api/v1/chat", json={})
    assert r.status_code == 422


def test_chat_success_mocked():
    fake = ChatResponse(reply="Вы входите в подземелье.",
                        timestamp="2025-01-01T00:00:00+00:00")
    with patch("app.api.v1.chat.chat_service.handle_message",
               new=AsyncMock(return_value=fake)):
        r = client.post("/api/v1/chat",
                        json={"message": "Иду вперёд"},
                        headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["reply"] == "Вы входите в подземелье."


def test_clear_history():
    user_id, token = register_user()
    r = client.delete(
        f"/api/v1/chat/history/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
