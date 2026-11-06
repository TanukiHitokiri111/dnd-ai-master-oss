"""
In-Memory Rate Limiter — thread-safe sliding window.

Единый движок для трёх независимых лимитов бэкенда (chat/auth, WS-флуд,
join-брутфорс): отличается только окно, порог и clock. Лимиты чата/авторизации
берут window/requests из settings; WS и sessions создают экземпляры со своими
константами, чтобы не влиять друг на друга.
"""

import asyncio
import time
from collections.abc import Callable

from app.config import settings
from app.exceptions import RateLimitError


class InMemoryRateLimiter:
    """Скользящее окно с периодической очисткой мёртвых ключей (async-safe)."""

    def __init__(self, *, window: float | None = None, max_requests: int | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._requests: dict[str, list[float]] = {}
        self._last_cleanup = clock()
        self._lock = asyncio.Lock()
        # None → настройки чата/авторизации из config (совместимость с v1)
        self._window = window if window is not None else settings.rate_limit_window
        self._max_requests = max_requests if max_requests is not None else settings.rate_limit_requests
        self._clock = clock

    def _cleanup_expired(self, now: float) -> None:
        dead = [
            key for key, times in self._requests.items()
            if not any(now - t <= self._window for t in times)
        ]
        for key in dead:
            del self._requests[key]

    def _hit_locked(self, key: str, now: float) -> bool:
        """Логика одного hit на захваченном локе: True = разрешено.

        Просроченные записи чистятся, превышение порога — False (текущий hit
        не записывается, как в исходном движке).
        """
        times = [t for t in self._requests.get(key, []) if now - t <= self._window]
        if len(times) >= self._max_requests:
            self._requests[key] = times
            return False
        times.append(now)
        self._requests[key] = times
        return True

    async def try_acquire(self, key: str) -> bool:
        """True = в лимите (hit записан), False = превышен (ничего не меняется)."""
        now = self._clock()

        async with self._lock:
            # Периодическая очистка (каждые 5 минут)
            if now - self._last_cleanup > 300:
                self._cleanup_expired(now)
                self._last_cleanup = now

            return self._hit_locked(key, now)

    async def check(self, key: str) -> None:
        """Бросить RateLimitError при превышении (API чата/авторизации)."""
        if not await self.try_acquire(key):
            raise RateLimitError(
                f"Слишком много запросов. Подождите {self._window:.0f} секунд."
            )


rate_limiter = InMemoryRateLimiter()
