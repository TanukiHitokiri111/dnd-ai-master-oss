     1|Апи можно использовать этот:
     2|
     3|fgt-your-key-here
     4|
     5|От форгет апи. Модель дипсик 4 флеш
     6|
     7|
     8|🐉 D&D AI Master — Финальный план разработки (v3, исправленная и дополненная)
     9|
    10|Я прошёлся по предыдущей версии как код-ревьюер и нашёл ещё 3 критических бага, из-за которых план не сработал бы даже при идеальном следовании инструкциям, плюс несколько пробелов. Ниже — полный автономный план: каждый файл приведён целиком, чистым кодом для копирования, без отсылок к несуществующим разделам.
    11|
    12|
    13|
    14|🔧 Что исправлено в ЭТОЙ версии
    15|
    16|№	Проблема предыдущей версии	Исправление
    17|1	🔴 Отсутствовали 3 файла виджетов — план отсылал к «исходному плану, разделы 3.10–3.12», которого у читателя нет. Новичок застрял бы навсегда	chat_message_tile.dart, chat_input.dart, dice_roller.dart написаны полностью (Этап 6)
    18|2	🔴 Dockerfile нерабочий: pip install --user кладёт пакеты в /root/.local, а контейнер запускается от appuser, у которого нет прав на /root (700). Контейнер падал бы с ModuleNotFoundError	Переписан на --prefix=/install → копирование в /usr/local (Этап 4)
    19|3	🔴 systemd EnvironmentFile ломал запуск: systemd съедает кавычки в CORS_ORIGINS=["*"] → pydantic получает [*] → ValidationError → сервис не стартует	EnvironmentFile убран; pydantic сам читает .env через WorkingDirectory (Этап 9.3)
    20|4	CORS: allow_credentials=True + allow_origins=["*"] — запрещённая комбинация по спецификации	allow_credentials=False
    21|5	class Config в pydantic-settings v2 — deprecated	SettingsConfigDict + extra="ignore"
    22|6	proguard-rules.pro упоминался в build.gradle, но файла не было → релизная сборка падала	Файл написан (Этап 8.4)
    23|7	Тесты падали без .env (импорт app требует OPENAI_API_KEY)	Добавлен conftest.py с фейковым ключом
    24|8	CI ожидал монорепозиторий (rpg_backend/ + rpg_client/), но git init делался внутри backend → вложенные репозитории, CI сломался бы	Единая структура dnd_ai/, один git init в корне
    25|9	Жёстко прошитые URL (flutter 3.24.3 tar.xz, cmdline-tools build 11076708) протухают через месяцы	Flutter ставится через git clone -b stable; для cmdline-tools — инструкция получения свежей ссылки
    26|10	rsync копировал локальный .env поверх серверного	Добавлен --exclude .env
    27|11	Не было шага «DNS A-запись» — certbot упал бы	Добавлен шаг с проверкой через ping (Этап 9.4)
    28|12	ChatState.copyWith: errorMessage молча сбрасывался при ЛЮБОМ вызове copyWith — неочевидный баг	Паттерн sentinel (_undefined) — корректное различие «не передан» и «null»
    29|13	WSL2: телефон не видит бэкенд (NAT), adb не видит USB	Блок «Если у вас Windows/WSL2»: portproxy + firewall + usbipd
    30|14	IP компьютера меняется по DHCP — приложение «внезапно» перестаёт работать	Правило «проверяйте IP каждую сессию» + точки, где менять
    31|15	TextField с maxLines: 5: кнопка Enter вставляла перенос вместо отправки	textInputAction: TextInputAction.send
    32|16	Нет оценок времени и денег	Добавлены ⏱ и 💰
    33|17	Нет теста rate-limiter'а	Добавлен (Этап 3.1)
    34|18	Нет дорожной карты после MVP	Этап 13
    35|
    36|⏱ Общее время: 8–12 часов активной работы (1–2 дня для новичка).
    37|💰 Бюджет: OpenAI — $5 (хватит на тысячи сообщений, gpt-4o-mini ≈ $0.0002/ответ) · VPS — 150–600 ₽/мес · домен — 150–1500 ₽/год · Google Play — $25 разово (опционально).
    38|
    39|
    40|
    41|ЭТАП 0. Подготовка (⏱ 40 мин)
    42|
    43|0.1. Что понадобится
    44|
    45|1.
    46|Компьютер: Ubuntu 22.04+ или Windows 10/11 с WSL2 (wsl --install в PowerShell от администратора, перезагрузка). 8 ГБ RAM, 30 ГБ свободного места.
    47|2.
    48|Аккаунт OpenAI: https://platform.openai.com → Settings → Billing → пополнить минимум на $5 (без этого API вернёт ошибку 429!).
    49|3.
    50|API-ключ: https://platform.openai.com/api-keys → «Create new secret key» → скопировать sk-... в надёжное место (показывается один раз).
    51|4.
    52|Аккаунт GitHub: https://github.com/signup
    53|5.
    54|Android-телефон + USB-кабель.
    55|
    56|0.2. Базовые инструменты
    57|
    58|sudo apt update && sudo apt upgrade -y
    59|sudo apt install -y git curl wget unzip xz-utils zip libglu1-mesa \
    60|  build-essential python3.11 python3.11-venv python3-pip openjdk-17-jdk
    61|git --version          # git version 2.x.x
    62|python3.11 --version   # Python 3.11.x
    63|java -version          # openjdk version "17..."
    64|bash
    65|
    66|
    67|0.3. Настройка Git
    68|
    69|git config --global user.name "Ваше Имя"
    70|git config --global user.email "ваш@email.com"
    71|git config --global init.defaultBranch main
    72|bash
    73|
    74|
    75|0.4. Отладка по USB на телефоне
    76|
    77|1.
    78|Настройки → О телефоне → 7 раз нажать «Номер сборки».
    79|2.
    80|Настройки → Для разработчиков → включить «Отладка по USB».
    81|3.
    82|Подключить кабелем к ПК → на телефоне нажать «Разрешить».
    83|
    84|0.5. Docker
    85|
    86|curl -fsSL https://get.docker.com | sudo sh
    87|sudo usermod -aG docker $USER
    88|newgrp docker
    89|docker ps   # НЕ должно быть ошибки. Если ошибка — перезагрузитесь.
    90|            # В WSL2 без systemd: sudo service docker start
    91|docker compose version
    92|bash
    93|
    94|
    95|0.6. 📌 Блок «Если у вас Windows (WSL2)» — прочитать обязательно
    96|
    97|В WSL2 есть две особенности, которые сломают план, если их не учесть:
    98|
    99|1. USB-телефон не виден в WSL. Лечится через usbipd (PowerShell от администратора, в Windows):
   100|
   101|winget install usbipd
   102|usbipd list                      # найдите BUSID телефона, например 1-4
   103|usbipd bind --busid 1-4
   104|usbipd attach --wsl --busid 1-4
   105|powershell
   106|
   107|
   108|После этого adb devices внутри WSL увидит телефон. После каждой перезагрузки Windows — повторять attach.
   109|
   110|
   111|2. Телефон не достучится до бэкенда в WSL2 (у WSL своя NAT-сеть). Решение — проброс порта (PowerShell от администратора):
   112|
   113|# узнайте IP WSL: в терминале WSL выполните  hostname -I
   114|netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.x.x.x
   115|New-NetFirewallRule -DisplayName "WSL2-8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   116|powershell
   117|
   118|
   119|В приложении указывайте IP Windows-машины (команда ipconfig → IPv4). ⚠️ IP WSL меняется после перезапуска — portproxy нужно будет обновлять.
   120|
   121|
   122|
   123|ЭТАП 1. Архитектура (⏱ 10 мин, только чтение)
   124|
   125|┌───────────────┐   HTTP/JSON    ┌───────────────┐   HTTPS   ┌────────────┐
   126|│  Flutter App  │ ◄────────────► │ FastAPI (Docker│ ◄────────► │ OpenAI API │
   127|│   (Android)   │  POST /api/v1/ │  / VPS, порт 8000)          │ gpt-4o-mini│
   128|└───────────────┘      chat      └───────────────┘           └────────────┘
   129|       │                                │
   130| SharedPreferences              In-memory история
   131| (история на устройстве,        (на MVP; продакшен —
   132|  переживает перезапуск)         Redis, см. Этап 13)
   133|text
   134|
   135|
   136|Поток одного сообщения: пользователь пишет → Flutter шлёт POST /api/v1/chat {user_id, message} → rate-limiter проверяет лимит → сервер добавляет сообщение к истории → OpenAI → ответ сохраняется в историю → JSON {reply, timestamp} → Flutter рисует Markdown.
   137|
   138|
   139|Порядок этапов не нарушать: 2 (бэкенд) → 3 (тесты) → 4 (Docker) → 5 (Flutter-окружение) → 6 (приложение) → 7 (Android) → 8 (релиз) → 9 (VPS) → 10 (CI).
   140|
   141|
   142|
   143|ЭТАП 2. Бэкенд (⏱ 1 час)
   144|
   145|2.1. Монорепозиторий и структура
   146|
   147|mkdir -p ~/projects/dnd_ai
   148|cd ~/projects/dnd_ai
   149|git init
   150|
   151|mkdir -p rpg_backend/app/api/v1 rpg_backend/app/services rpg_backend/tests
   152|cd rpg_backend
   153|touch app/__init__.py app/main.py app/models.py app/config.py app/exceptions.py app/logger.py
   154|touch app/api/__init__.py app/api/v1/__init__.py app/api/v1/chat.py
   155|touch app/services/__init__.py app/services/chat_service.py app/services/rate_limiter.py
   156|touch tests/__init__.py tests/test_chat.py tests/test_service.py
   157|touch conftest.py pytest.ini requirements.txt Dockerfile docker-compose.yml \
   158|      .env.example .dockerignore
   159|cd ..
   160|bash
   161|
   162|
   163|Итоговая структура репозитория:
   164|
   165|dnd_ai/
   166|├── .gitignore                  (общий, создаём на шаге 2.2)
   167|├── .github/workflows/build.yml (Этап 10)
   168|├── rpg_backend/
   169|│   ├── app/
   170|│   │   ├── main.py             — точка входа FastAPI
   171|│   │   ├── config.py           — настройки из .env
   172|│   │   ├── models.py           — Pydantic-модели
   173|│   │   ├── exceptions.py       — исключения
   174|│   │   ├── logger.py           — логирование
   175|│   │   ├── api/v1/chat.py      — роутер /chat
   176|│   │   └── services/
   177|│   │       ├── chat_service.py — бизнес-логика + OpenAI
   178|│   │       └── rate_limiter.py — защита от спама
   179|│   ├── tests/ + conftest.py + pytest.ini
   180|│   └── .env / requirements.txt / Dockerfile / docker-compose.yml
   181|└── rpg_client/                 (Flutter, Этап 6)
   182|text
   183|
   184|
   185|2.2. Корневой .gitignore (~/projects/dnd_ai/.gitignore)
   186|
   187|# ===== СЕКРЕТЫ — никогда не коммитить! =====
   188|.env
   189|**/key.properties
   190|*.jks
   191|*.keystore
   192|
   193|# ===== Python =====
   194|__pycache__/
   195|*.pyc
   196|venv/
   197|.pytest_cache/
   198|.ruff_cache/
   199|*.log
   200|
   201|# ===== Flutter/Dart =====
   202|.dart_tool/
   203|build/
   204|gitignore
   205|
   206|
   207|2.3. app/logger.py
   208|
   209|import logging
   210|import sys
   211|
   212|
   213|def setup_logger(name: str = "rpg") -> logging.Logger:
   214|    """Единый логгер. Пишет в stdout — Docker и systemd журналируют его сами."""
   215|    logger = logging.getLogger(name)
   216|    if logger.handlers:  # защита от дублирования при повторном импорте
   217|        return logger
   218|    logger.setLevel(logging.INFO)
   219|    handler = logging.StreamHandler(sys.stdout)
   220|    handler.setFormatter(logging.Formatter(
   221|        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
   222|    ))
   223|    logger.addHandler(handler)
   224|    return logger
   225|
   226|
   227|logger = setup_logger()
   228|python
   229|
   230|
   231|2.4. app/config.py (исправлено под pydantic v2)
   232|
   233|from functools import lru_cache
   234|from pydantic_settings import BaseSettings, SettingsConfigDict
   235|
   236|
   237|class Settings(BaseSettings):
   238|    """Все настройки — из .env. Ни одного секрета в коде!"""
   239|
   240|    model_config = SettingsConfigDict(
   241|        env_file=".env",
   242|        env_file_encoding="utf-8",
   243|        extra="ignore",  # не падать, если в окружении есть лишние переменные
   244|    )
   245|
   246|    # OpenAI
   247|    openai_api_key: str
   248|    model: str = "gpt-4o-mini"      # дёшево. Для продакшена: "gpt-4o"
   249|    max_history_length: int = 20
   250|    openai_timeout: float = 60.0
   251|
   252|    # Rate limiting: N запросов за окно (сек) на одного пользователя
   253|    rate_limit_requests: int = 10
   254|    rate_limit_window: int = 60
   255|
   256|    system_prompt: str = (
   257|        "Ты — опытный мастер Dungeons & Dragons 5e. "
   258|        "Описывай сцены красочно, но лаконично (до 200 слов). "
   259|        "После каждого описания предлагай игроку 2-3 варианта действий списком. "
   260|        "Используй Markdown: **жирный** для важного, списки для вариантов. "
   261|        "Если игрок сообщает результат броска кубика — учитывай его по правилам D&D 5e. "
   262|        "Никогда не выходи из роли мастера игры."
   263|    )
   264|
   265|    app_name: str = "D&D AI Master"
   266|    debug: bool = False
   267|    cors_origins: list[str] = ["*"]
   268|
   269|
   270|@lru_cache()
   271|def get_settings() -> Settings:
   272|    return Settings()
   273|
   274|
   275|settings = get_settings()
   276|python
   277|
   278|
   279|2.5. app/exceptions.py
   280|
   281|class RPGException(Exception):
   282|    """Базовое исключение приложения."""
   283|
   284|
   285|class OpenAIError(RPGException):
   286|    """Ошибка при обращении к OpenAI API."""
   287|
   288|
   289|class ValidationError(RPGException):
   290|    """Ошибка валидации входных данных."""
   291|
   292|
   293|class RateLimitError(RPGException):
   294|    """Превышен лимит запросов."""
   295|python
   296|
   297|
   298|2.6. app/models.py
   299|
   300|from pydantic import BaseModel, Field, field_validator
   301|
   302|
   303|class ChatRequest(BaseModel):
   304|    user_id: str = Field(..., min_length=1, max_length=64,
   305|                         description="Уникальный ID пользователя (UUID)")
   306|    message: str = Field(..., min_length=1, max_length=4000,
   307|                         description="Сообщение игрока")
   308|
   309|    @field_validator("user_id", "message")
   310|    @classmethod
   311|    def not_blank(cls, v: str) -> str:
   312|        if not v.strip():
   313|            raise ValueError("Поле не может состоять из пробелов")
   314|        return v.strip()
   315|
   316|
   317|class ChatResponse(BaseModel):
   318|    reply: str = Field(..., description="Ответ AI-мастера (Markdown)")
   319|    timestamp: str = Field(..., description="Время ответа, ISO 8601 UTC")
   320|
   321|
   322|class HealthResponse(BaseModel):
   323|    status: str
   324|    version: str = "1.0.0"
   325|python
   326|
   327|
   328|2.7. app/services/rate_limiter.py
   329|
   330|import time
   331|from collections import defaultdict, deque
   332|from app.config import settings
   333|from app.exceptions import RateLimitError
   334|
   335|
   336|class InMemoryRateLimiter:
   337|    """
   338|    Скользящее окно: хранит время последних запросов каждого пользователя.
   339|    Для MVP достаточно; с несколькими воркерами нужен Redis (Этап 13).
   340|    """
   341|
   342|    def __init__(self):
   343|        self._requests: dict[str, deque] = defaultdict(deque)
   344|
   345|    def check(self, user_id: str) -> None:
   346|        now = time.monotonic()
   347|        window = settings.rate_limit_window
   348|        q = self._requests[user_id]
   349|
   350|        while q and now - q[0] > window:  # выбрасываем устаревшие записи
   351|            q.popleft()
   352|
   353|        if len(q) >= settings.rate_limit_requests:
   354|            raise RateLimitError(
   355|                f"Слишком много запросов. Подождите {window} секунд."
   356|            )
   357|        q.append(now)
   358|
   359|
   360|rate_limiter = InMemoryRateLimiter()
   361|python
   362|
   363|
   364|2.8. app/services/chat_service.py
   365|
   366|from collections import defaultdict
   367|from datetime import datetime, timezone
   368|from typing import Dict, List
   369|from openai import AsyncOpenAI, APIError, RateLimitError as OpenAIRateLimit
   370|from app.config import settings
   371|from app.models import ChatRequest, ChatResponse
   372|from app.exceptions import OpenAIError, RateLimitError
   373|from app.logger import logger
   374|
   375|
   376|class ChatService:
   377|    """
   378|    История диалогов + общение с OpenAI.
   379|    ⚠️ История в памяти: теряется при рестарте и НЕ работает с >1 воркером.
   380|    Для MVP — норма. Для продакшена — Redis (Этап 13).
   381|    """
   382|
   383|    def __init__(self, client: AsyncOpenAI | None = None):
   384|        # client подменяется в тестах (dependency injection)
   385|        self.client = client or AsyncOpenAI(
   386|            api_key=settings.openai_api_key,
   387|            timeout=settings.openai_timeout,
   388|        )
   389|        self.histories: Dict[str, List[dict]] = defaultdict(list)
   390|
   391|    def _get_history(self, user_id: str) -> List[dict]:
   392|        history = self.histories[user_id]
   393|        if not history:
   394|            history.append({"role": "system", "content": settings.system_prompt})
   395|        return history
   396|
   397|    def _trim_history(self, history: List[dict]) -> List[dict]:
   398|        """Системный промпт (первый) + последние N сообщений."""
   399|        if len(history) <= settings.max_history_length + 1:
   400|            return history
   401|        return [history[0]] + history[-settings.max_history_length:]
   402|
   403|    async def handle_message(self, request: ChatRequest) -> ChatResponse:
   404|        history = self._get_history(request.user_id)
   405|        history.append({"role": "user", "content": request.message})
   406|        history = self._trim_history(history)
   407|        self.histories[request.user_id] = history
   408|
   409|        logger.info(f"user={request.user_id[:8]} → OpenAI, history={len(history)} msgs")
   410|
   411|        try:
   412|            response = await self.client.chat.completions.create(
   413|                model=settings.model,
   414|                messages=history,
   415|                temperature=0.8,
   416|                max_tokens=1500,
   417|                presence_penalty=0.2,
   418|            )
   419|        except OpenAIRateLimit:
   420|            self._rollback(history)
   421|            logger.warning("OpenAI rate limit hit")
   422|            raise RateLimitError("Превышен лимит OpenAI. Попробуйте через минуту.")
   423|        except APIError as e:
   424|            self._rollback(history)
   425|            logger.error(f"OpenAI APIError: {e}")
   426|            raise OpenAIError("Ошибка AI-сервиса. Попробуйте позже.")
   427|        except Exception as e:
   428|            self._rollback(history)
   429|            logger.exception("Unexpected error")
   430|            raise OpenAIError(f"Неожиданная ошибка: {e}")
   431|
   432|        reply = response.choices[0].message.content or ""
   433|        history.append({"role": "assistant", "content": reply})
   434|        self.histories[request.user_id] = history
   435|
   436|        return ChatResponse(
   437|            reply=reply,
   438|            timestamp=datetime.now(timezone.utc).isoformat(),
   439|        )
   440|
   441|    @staticmethod
   442|    def _rollback(history: List[dict]) -> None:
   443|        """Убираем сообщение пользователя, на которое не получен ответ."""
   444|        if history and history[-1]["role"] == "user":
   445|            history.pop()
   446|
   447|    def clear_history(self, user_id: str) -> None:
   448|        self.histories.pop(user_id, None)
   449|        logger.info(f"history cleared for user={user_id[:8]}")
   450|
   451|
   452|chat_service = ChatService()
   453|python
   454|
   455|
   456|2.9. app/api/v1/chat.py
   457|
   458|from fastapi import APIRouter, HTTPException, status
   459|from app.models import ChatRequest, ChatResponse
   460|from app.services.chat_service import chat_service
   461|from app.services.rate_limiter import rate_limiter
   462|from app.exceptions import OpenAIError, RateLimitError
   463|from app.logger import logger
   464|
   465|router = APIRouter(prefix="/chat", tags=["Chat"])
   466|
   467|
   468|@router.post("", response_model=ChatResponse)
   469|async def chat_endpoint(request: ChatRequest):
   470|    """Основной endpoint общения с AI-мастером."""
   471|    try:
   472|        rate_limiter.check(request.user_id)
   473|        return await chat_service.handle_message(request)
   474|    except RateLimitError as e:
   475|        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
   476|    except OpenAIError as e:
   477|        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
   478|    except HTTPException:
   479|        raise
   480|    except Exception:
   481|        logger.exception("Unhandled error in /chat")
   482|        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
   483|                            detail="Внутренняя ошибка сервера")
   484|
   485|
   486|@router.delete("/history/{user_id}")
   487|async def clear_history(user_id: str):
   488|    """Очистить историю диалога на сервере."""
   489|    chat_service.clear_history(user_id)
   490|    return {"message": "История очищена"}
   491|python
   492|
   493|
   494|2.10. app/main.py (исправлен CORS)
   495|
   496|from contextlib import asynccontextmanager
   497|from fastapi import FastAPI
   498|from fastapi.middleware.cors import CORSMiddleware
   499|from app.config import settings
   500|from app.api.v1.chat import router as chat_router
   501|