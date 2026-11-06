# Этап 1: сборка зависимостей
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Этап 2: продакшен-образ
FROM python:3.11-slim
WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY cron_expire.py ./
# Контент мира (расы, классы, предыстории, навыки, языки) — часть образа.
# Пользовательская база и картинки живут в /app/data поверх этого (volume).
COPY data/*.json ./data/

# Создаём папку для SQLite, пользователя и gosu (сброс прав при старте)
RUN mkdir -p /app/data \
 && useradd -m -u 1000 appuser \
 && chown -R appuser:appuser /app \
 && apt-get update \
 && apt-get install -y --no-install-recommends gosu \
 && rm -rf /var/lib/apt/lists/*

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "app.main:app", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-"]
