#!/bin/sh
# Контейнер стартует от root только для того, чтобы привести права на /app/data
# к нужному владельцу: каталог приходит из bind-mount и может принадлежать
# другому пользователю (установка на macOS, другой UID на Linux).
# Дальше приложение работает от непривилегированного appuser.
set -e

if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R appuser:appuser /app/data 2>/dev/null || true
    exec gosu appuser "$@"
fi

exec "$@"
