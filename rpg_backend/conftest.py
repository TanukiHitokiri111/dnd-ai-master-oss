"""Общие настройки pytest: фейковое окружение и хелперы для тестов API.

Тесты не ходят в сеть и не тратят деньги: провайдер подменяется моками,
а пользователя для авторизации регистрируем настоящего — в тестовой базе.
"""

import os
import uuid

os.environ.setdefault("LLM_API_KEY", "test-fake-key-for-pytest")
os.environ.setdefault("LLM_API_BASE_URL", "https://example.com/v1")
os.environ.setdefault("MODEL", "test-model")
os.environ.setdefault("JWT_SECRET", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("REQUIRE_ACCESS", "false")

import asyncio  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

# Схема должна существовать до первого запроса: TestClient без контекстного
# менеджера не запускает lifespan приложения.
asyncio.run(init_db())

# Фоновая суммаризация памяти ходит в LLM. В тестах это лишний сетевой вызов,
# из-за которого процесс pytest не завершается — глушим её.
from app.services.chat_service import ChatService  # noqa: E402


async def _no_summarize(*args, **kwargs):
    return None


ChatService._maybe_summarize = _no_summarize

client = TestClient(app)


def register_user() -> tuple[str, str]:
    """Зарегистрировать нового пользователя. Возвращает (user_id, token)."""
    username = f"pytest_{uuid.uuid4().hex[:10]}"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["user_id"], data["token"]


def auth_headers() -> dict:
    """Заголовок Authorization с токеном свежего пользователя."""
    _, token = register_user()
    return {"Authorization": f"Bearer {token}"}