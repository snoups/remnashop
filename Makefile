ALEMBIC_INI=src/infrastructure/database/alembic.ini
DATABASE_HOST ?= 0.0.0.0
DATABASE_PORT ?= 6767

LOCAL_DB_ENV := DATABASE_HOST=$(DATABASE_HOST) DATABASE_PORT=$(DATABASE_PORT)

RESET := $(filter reset,$(MAKECMDGOALS))

.PHONY: setup-env
setup-env:
	@sed -i '' "s|^APP_CRYPT_KEY=.*|APP_CRYPT_KEY=$(shell openssl rand -base64 32 | tr -d '\n')|" .env
	@sed -i '' "s|^BOT_SECRET_TOKEN=.*|BOT_SECRET_TOKEN=$(shell openssl rand -hex 64 | tr -d '\n')|" .env
	@sed -i '' "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@sed -i '' "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@echo "Secrets updated. Check your .env file"

# ── Run ────────────────────────────────────────────────────────────────────────

.PHONY: run
run: _run_local

.PHONY: run-local
run-local: _run_local

.PHONY: run-prod
run-prod: _run_prod

.PHONY: _run_local
_run_local:
ifneq ($(RESET),)
	@docker compose -f docker-compose.local.yml down -v
endif
	@docker compose -f docker-compose.local.yml up --build
	@docker compose logs -f

.PHONY: _run_prod
_run_prod:
ifneq ($(RESET),)
	@docker compose -f docker-compose.prod.external.yml down -v
endif
	@docker compose -f docker-compose.prod.external.yml up --build
	@docker compose logs -f

# ── Migrations ─────────────────────────────────────────────────────────────────

.PHONY: migration
migration:
	alembic -c $(ALEMBIC_INI) revision --autogenerate

.PHONY: migration-local
migration-local:
	$(LOCAL_DB_ENV) alembic -c $(ALEMBIC_INI) revision --autogenerate

.PHONY: migrate
migrate:
	alembic -c $(ALEMBIC_INI) upgrade head

.PHONY: migrate-local
migrate-local:
	$(LOCAL_DB_ENV) alembic -c $(ALEMBIC_INI) upgrade head

.PHONY: downgrade
downgrade:
	@if [ -z "$(rev)" ]; then \
		echo "No revision specified. Downgrading by 1 step."; \
		alembic -c $(ALEMBIC_INI) downgrade -1; \
	else \
		alembic -c $(ALEMBIC_INI) downgrade $(rev); \
	fi

.PHONY: downgrade-local
downgrade-local:
	@if [ -z "$(rev)" ]; then \
		echo "No revision specified. Downgrading by 1 step."; \
		$(LOCAL_DB_ENV) alembic -c $(ALEMBIC_INI) downgrade -1; \
	else \
		$(LOCAL_DB_ENV) alembic -c $(ALEMBIC_INI) downgrade $(rev); \
	fi

# ── Misc ───────────────────────────────────────────────────────────────────────

.PHONY: reset
reset:
	@: