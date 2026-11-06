import os
from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки — из .env. Ни одного секрета в коде!"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Провайдер LLM — любой OpenAI-совместимый API.
    # Старые имена (FORGET_API_KEY / FORGET_API_BASE_URL) тоже принимаются,
    # чтобы не ломать уже настроенные .env.
    llm_api_key: str = Field(validation_alias=AliasChoices("LLM_API_KEY", "FORGET_API_KEY"))
    llm_api_base_url: str = Field(
        "https://api.openai.com/v1",
        validation_alias=AliasChoices("LLM_API_BASE_URL", "FORGET_API_BASE_URL"),
    )
    model: str = "deepseek-chat"  # любая модель вашего OpenAI-совместимого провайдера
    appearance_prompt_model: str = "deepseek-chat"  # модель для промпта внешности
    # Генерация портретов: OpenAI-совместимый шлюз с image-моделью.
    # Пусто — портреты отключены (игра работает без картинок).
    image_api_url: str = ""
    # Запасной путь: обычный /images/generations, ответ в b64_json.
    image_api_alt_url: str = ""
    image_api_alt_key: str = ""
    image_api_alt_model: str = "gpt-image-1"

    # Auth
    jwt_secret: str = ""  # Обязательно задать в .env

    # Админы (user_id через запятую)
    admin_user_ids: str = ""  # user_id через запятую; пусто = админов нет

    # Платный доступ. True — каждый запрос проверяет is_active и подписку,
    # новые пользователи ждут активации. False (по умолчанию) — доступ открыт
    # всем зарегистрированным, режим «просто поиграть».
    require_access: bool = False

    # Boosty API (legacy — replaced by YooKassa)
    boosty_api_token: str = ""
    boosty_url: str = ""
    boosty_blog: str = ""  # имя блога Boosty для синхронизации подписчиков

    # YooKassa payments
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_test_mode: bool = True  # True = test shop, False = production
    yookassa_return_url: str = "http://localhost:8000/"

    max_history_length: int = 20  # сообщений в контексте (поднято с 12 — модель теряла нарратив)
    api_timeout: float = 120.0  # AI может думать долго

    # Rate limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60

    system_prompt: str = (
        "Ты — опытный мастер Dungeons & Dragons 5e. "
        "Описывай сцены красочно, атмосферно, погружай игрока в мир. "
        "НИКОГДА не предлагай варианты действий — ни списком, ни в тексте. "
        "Игрок сам решает что делать. Твоя задача — описывать мир и реагировать на действия игрока. "
        "Используй Markdown: **жирный** для имён и важных предметов. "
        "Никогда не выходи из роли мастера игры. "
        "Романтические сцены отыгрываются с проверками навыков (Убеждение/Выступление/Ловкость рук)."
    )

    app_name: str = "D&D AI Master"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]


# Необязательный фильтр провайдеров для агрегаторов вроде OpenRouter/polza.
# По умолчанию выключен: extra_body=None — запрос идёт без навязывания провайдера.
# Задать, если нужно: PROVIDER_FILTER="streamlake/fp8,gmicloud/fp8" в .env
_provider_filter = [p.strip() for p in os.environ.get("PROVIDER_FILTER", "").split(",") if p.strip()]
POLZA_EXTRA_BODY: dict | None = (
    {"provider": {"only": _provider_filter, "allow_fallbacks": True}} if _provider_filter else None
)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
