"""Тесты chat_service + rate_limiter."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import settings
from app.models import ChatRequest
from app.services.chat_service import ChatService, chat_service
from app.services.rate_limiter import InMemoryRateLimiter
from app.exceptions import AIError, RateLimitError


def make_mock_client(reply: str = "Добро пожаловать в таверну!"):
    """Фейковый клиент — тесты не тратят деньги и не ходят в сеть."""
    client = MagicMock()
    message = MagicMock()
    message.content = reply
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_handle_message_returns_reply():
    service = ChatService(client=make_mock_client())
    result = await service.handle_message(
        ChatRequest(user_id="test-user", message="Захожу в таверну")
    )
    assert result.reply == "Добро пожаловать в таверну!"
    assert result.timestamp


@pytest.mark.asyncio
async def test_history_persists_in_db():
    """После сообщения история сохраняется в БД и загружается обратно."""
    service = ChatService(client=make_mock_client())
    await service.handle_message(ChatRequest(user_id="db-user-1", message="Привет"))

    # Загружаем историю -> должен быть system prompt + user + assistant
    history = await service._get_history("db-user-1")
    assert history[0]["role"] == "system"
    assert any(m["role"] == "user" and m["content"] == "Привет" for m in history)
    assert any(m["role"] == "assistant" for m in history)

    # Чистим и убеждаемся что история пустая (только system)
    await service.clear_history("db-user-1")
    after_clear = await service._get_history("db-user-1")
    assert len(after_clear) == 1  # только system
    assert after_clear[0]["role"] == "system"


@pytest.mark.asyncio
async def test_error_does_not_save_message():
    """При ошибке API сообщение пользователя НЕ сохраняется в БД."""
    client = make_mock_client()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    service = ChatService(client=client)

    with pytest.raises(AIError):
        await service.handle_message(ChatRequest(user_id="err-user", message="Тест"))

    # В БД не должно быть сообщений (только system в _get_history)
    history = await service._get_history("err-user")
    assert all(m["role"] == "system" for m in history)
    # И чистим за собой
    await service.clear_history("err-user")


@pytest.mark.asyncio
async def test_clear_history():
    service = ChatService(client=make_mock_client())
    await service.handle_message(ChatRequest(user_id="u3", message="раз"))
    await service.handle_message(ChatRequest(user_id="u3", message="два"))

    history_before = await service._get_history("u3")
    assert len(history_before) > 1  # system + messages

    await service.clear_history("u3")
    history_after = await service._get_history("u3")
    assert len(history_after) == 1
    assert history_after[0]["role"] == "system"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(settings.rate_limit_requests):
        await limiter.check("spammer")
    with pytest.raises(RateLimitError):
        await limiter.check("spammer")


@pytest.mark.asyncio
async def test_rate_limiter_ignores_other_users():
    limiter = InMemoryRateLimiter()
    for _ in range(settings.rate_limit_requests):
        await limiter.check("user-a")
    await limiter.check("user-b")  # не должно упасть
