.PHONY: help install up down logs test lint build-web backup

help:
	@echo "D&D AI Master"
	@echo ""
	@echo "  make install    — установка с нуля (./install.sh)"
	@echo "  make up         — поднять контейнер"
	@echo "  make down       — остановить"
	@echo "  make logs       — логи сервиса"
	@echo "  make test       — тесты бэкенда"
	@echo "  make lint       — проверка стиля Python"
	@echo "  make build-web  — пересобрать веб-клиент"
	@echo "  make backup     — копия базы и картинок"

install:
	./install.sh

up:
	cd rpg_backend && docker compose up -d --build

down:
	cd rpg_backend && docker compose down

logs:
	cd rpg_backend && docker compose logs -f --tail 100

test:
	cd rpg_backend && pytest -q

lint:
	cd rpg_backend && ruff check app

build-web:
	cd rpg_client && flutter build web --base-href / --dart-define=API_BASE_URL=
	rsync -a --exclude='buy.html' rpg_client/build/web/ rpg_backend/app/static/

backup:
	@mkdir -p backups
	@tar czf backups/data-$$(date +%Y%m%d-%H%M%S).tar.gz -C rpg_backend data
	@echo "Готово: $$(ls -t backups/*.tar.gz | head -1)"