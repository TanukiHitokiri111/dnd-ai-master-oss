from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.db import init_db
from app.api.v1.chat import router as chat_router
from app.api.v1.auth import router as auth_router
from app.api.v1.characters import router as characters_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.friends import router as friends_router
from app.api.v1.ws import router as ws_router
from app.api.v1.admin import router as admin_router
from app.api.v1.worlds import router as worlds_router


class NoGzipStreamMiddleware:
    """GZip для обычных ответов, но НЕ для SSE-потоков.

    GZipMiddleware из starlette буферизует ВЕСЬ ответ (включая text/event-stream)
    и отдаёт его браузеру одним куском — стриминг превращается в
    «долгое ожидание → весь текст разом». Пути /chat/stream пропускаем без сжатия.
    """

    _NO_GZIP_PATHS = ("/api/v1/chat/stream", "/api/v1/ws")

    def __init__(self, app, minimum_size: int = 500):
        self.app = app
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self._NO_GZIP_PATHS:
            await self.app(scope, receive, send)
        else:
            await self._gzip(scope, receive, send)

from app.api.v1.payments import router as payments_router
from app.models import HealthResponse
from app.logger import logger
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"\U0001f680 Запуск {settings.app_name}, модель: {settings.model}")
    await init_db()
    logger.info("\u2713 База данных инициализирована")
    yield
    logger.info("\U0001f6d1 Остановка сервера")


app = FastAPI(
    title=settings.app_name,
    description="RPG-чат с AI-мастером для D&D v3.0.0.20 — мультиплеер",
    version="3.0.0.21",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip: сжимаем всё что больше 500 байт — JS/WASM летят в 3-4 раза быстрее.
# ВАЖНО: SSE-стриминг (/chat/stream) НЕ сжимаем — GZipMiddleware буферизует
# весь поток и отдаёт браузеру одним куском, убивая стриминг.
app.add_middleware(NoGzipStreamMiddleware, minimum_size=500)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(characters_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(friends_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(worlds_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy")


@app.get("/api/v1/status")
async def api_status():
    return {"status": "ok", "version": "3.0.0.21"}


# ─── Статика (Flutter Web SPA) — безопасный catch-all ───

_STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parent / "static")).resolve()
_INDEX_FILE = _STATIC_DIR / "index.html"
_API_PREFIXES = ("/api/", "/health", "/docs", "/redoc", "/openapi.json", "/ws")

# Расширения для долгоживущего кеша (иммутабельные ассеты с хешем в имени)
_CACHE_IMMUTABLE = {".js", ".wasm", ".mjs", ".png", ".jpg", ".webp", ".svg", ".woff2"}

# Расширения для короткого кеша (HTML, CSS, JSON — могут меняться)
_CACHE_SHORT = {".html", ".css", ".json", ".ico"}

# MIME-типы, которые Starlette не знает (wasm = application/json по умолчанию)
_MIME_OVERRIDES = {
    ".wasm": "application/wasm",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
}


def _get_media_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return _MIME_OVERRIDES.get(suffix)


def _is_api_path(path: str) -> bool:
    return any(path.startswith(p) for p in _API_PREFIXES)


def _resolve_static(rel: str) -> Path | None:
    """Безопасное разрешение пути — строго внутри STATIC_DIR. ValueError от relative_to ловится внутри."""
    if not rel or "\x00" in rel or "\\" in rel:
        return None
    candidate = (_STATIC_DIR / rel.lstrip("/")).resolve()
    try:
        candidate.relative_to(_STATIC_DIR)
    except ValueError:
        return None
    return candidate


@app.get("/api/v1/data/scenes/{filename:path}")
async def serve_scene_image(filename: str = ""):
    """Отдать сгенерированную картинку локации из /app/data/scenes."""
    # Запрос без filename → 404, а не 422
    if not filename:
        return Response("Not found", status_code=404)
    safe = Path(filename).name  # только имя файла, без путей
    scene_path = Path("/app/data/scenes") / safe
    if scene_path.is_file() and scene_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        return FileResponse(str(scene_path), media_type=media.get(scene_path.suffix.lower(), "image/png"))
    return Response("Not found", status_code=404)


@app.get("/{full_path:path}")
async def serve_static(full_path: str, request: Request):
    # API-пути — 404, а не index.html
    if _is_api_path(request.url.path):
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    # Защита от null-байта
    if "\x00" in full_path:
        return JSONResponse({"detail": "Bad Request"}, status_code=400)

    # Пустой путь → index.html
    if not full_path:
        if _INDEX_FILE.is_file():
            return FileResponse(str(_INDEX_FILE), media_type="text/html")
        return Response("Not found", status_code=404)

    # Безопасное разрешение
    file_path = _resolve_static(full_path)
    if file_path is None:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if file_path.is_file():
        media_type = _get_media_type(file_path)
        suffix = file_path.suffix.lower()
        # Кеш: JS/WASM — год, HTML/CSS — час
        headers = {}
        if suffix in _CACHE_IMMUTABLE:
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif suffix in _CACHE_SHORT:
            headers["Cache-Control"] = "public, max-age=3600"
        # index.html и flutter_bootstrap.js никогда не кэшировать
        if file_path.name in ("index.html", "flutter_bootstrap.js"):
            headers["Cache-Control"] = "no-cache"
        return FileResponse(str(file_path), media_type=media_type, headers=headers) if media_type else FileResponse(str(file_path), headers=headers)

    # SPA fallback
    if _INDEX_FILE.is_file():
        return FileResponse(str(_INDEX_FILE), media_type="text/html", headers={"Cache-Control": "no-cache"})
    return Response("Not found", status_code=404)
