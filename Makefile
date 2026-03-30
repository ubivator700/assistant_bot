.PHONY: install dev migrate logs logs-prod shell deploy backup-db up down webhook-setup webhook-remove service-install

# ── Разработка ────────────────────────────────────────────────────────────────

install:
	pip install -r requirements.txt

dev:
	python main.py

migrate:
	python -m alembic upgrade head

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f bot

shell:
	docker compose exec bot bash

# ── Деплой на VPS ─────────────────────────────────────────────────────────────

deploy:
	git pull
	pip install -r requirements.txt
	python -m alembic upgrade head
	sudo systemctl restart assistant-bot
	@echo "✅ Деплой завершён"

backup-db:
	docker compose exec mysql mysqldump \
		-u $${MYSQL_USER:-assistant} \
		-p$${MYSQL_PASSWORD} \
		$${MYSQL_DB:-assistant_bot} \
		> backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Бэкап создан"

# ── Webhook ───────────────────────────────────────────────────────────────────

webhook-setup:
	python setup_webhook.py setup

webhook-remove:
	python setup_webhook.py remove

# ── systemd (запускать на VPS) ────────────────────────────────────────────────

service-install:
	sudo cp assistant-bot.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable assistant-bot
	sudo systemctl start assistant-bot
	@echo "✅ Сервис установлен и запущен"

logs-prod:
	sudo journalctl -u assistant-bot -f
