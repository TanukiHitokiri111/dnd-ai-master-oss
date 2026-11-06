#!/usr/bin/env bash
# ============================================================
#  D&D AI Master — установка одной командой.
#  Запуск:  ./install.sh
#  Требуется: Docker с плагином compose (docker compose version).
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/rpg_backend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
say()  { printf "${GREEN}==>${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}!!${NC}  %s\n" "$*"; }
die()  { printf "${RED}XX${NC}  %s\n" "$*"; exit 1; }

# --- 1. Проверка Docker -------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker не установлен. Поставьте его: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "Нет плагина docker compose. Установите docker-compose-plugin."
docker info >/dev/null 2>&1 || die "Демон Docker не запущен (или нет прав). Попробуйте: sudo systemctl start docker"

# --- 2. Файл настроек ---------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  say "Создан .env из шаблона."
fi

# --- 3. Секрет для JWT --------------------------------------
if grep -qE '^JWT_SECRET=$' .env || ! grep -q '^JWT_SECRET=' .env; then
  SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
  if grep -q '^JWT_SECRET=' .env; then
    sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${SECRET}|" .env && rm -f .env.bak
  else
    printf 'JWT_SECRET=%s\n' "$SECRET" >> .env
  fi
  say "Сгенерирован JWT_SECRET."
fi

# --- 4. Проверка ключа провайдера ---------------------------
if grep -q '^LLM_API_KEY=your-api-key-here' .env || grep -qE '^LLM_API_KEY=$' .env; then
  warn "В .env не указан ключ провайдера."
  warn "Откройте rpg_backend/.env и заполните:"
  warn "    LLM_API_KEY, LLM_API_BASE_URL, MODEL"
  warn "Подойдёт любой OpenAI-совместимый API (OpenAI, OpenRouter, DeepSeek, Ollama...)."
  echo
  read -r -p "Ввести ключ сейчас? [y/N] " REPLY
  if [[ "${REPLY:-N}" =~ ^[Yy]$ ]]; then
    read -r -p "  Ключ: " KEY
    read -r -p "  Адрес API [https://api.deepseek.com/v1]: " BASE
    read -r -p "  Модель [deepseek-chat]: " MDL
    BASE=${BASE:-https://api.deepseek.com/v1}
    MDL=${MDL:-deepseek-chat}
    sed -i.bak "s|^LLM_API_KEY=.*|LLM_API_KEY=${KEY}|; s|^LLM_API_BASE_URL=.*|LLM_API_BASE_URL=${BASE}|; s|^MODEL=.*|MODEL=${MDL}|" .env && rm -f .env.bak
    say "Ключ записан."
  else
    die "Заполните rpg_backend/.env и запустите ./install.sh снова."
  fi
fi

# --- 5. Сборка и запуск -------------------------------------
PORT=$(grep -E '^APP_PORT=' .env | cut -d= -f2 | tr -d ' \r')
PORT=${PORT:-8000}
say "Собираю образ (первый раз это 2-3 минуты)..."
docker compose up -d --build

# --- 6. Ожидание готовности ---------------------------------
say "Жду, пока поднимется сервис..."
for i in $(seq 1 60); do
  if curl -fsS --noproxy '*' "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo
    say "Готово. Откройте: http://localhost:${PORT}"
    say "Регистрация нового пользователя — на главной странице."
    exit 0
  fi
  sleep 2
done

echo
warn "Сервис не ответил за 2 минуты. Логи:"
docker compose logs --tail 50
exit 1