ALEMBIC_INI=src/infrastructure/database/alembic.ini

.PHONY: setup-env
setup-env:
	@sed -i '' "s|^APP_CRYPT_KEY=.*|APP_CRYPT_KEY=$(shell openssl rand -base64 32 | tr -d '\n')|" .env
	@sed -i '' "s|^BOT_SECRET_TOKEN=.*|BOT_SECRET_TOKEN=$(shell openssl rand -hex 64 | tr -d '\n')|" .env
	@sed -i '' "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@sed -i '' "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(shell openssl rand -hex 24 | tr -d '\n')|" .env
	@echo "Secrets updated. Check your .env file"

.PHONY: migration
migration:
	alembic -c $(ALEMBIC_INI) revision --autogenerate

.PHONY: migrate
migrate:
	alembic -c $(ALEMBIC_INI) upgrade head

.PHONY: downgrade
downgrade:
ifndef rev
	$(error rev is undefined. Use: make downgrade rev=<revision>)
endif
	alembic -c $(ALEMBIC_INI) downgrade $(rev)

.PHONY: run-local
run-local:
	@docker compose -f docker-compose.local.yml up --build
	@docker compose logs -f
	
.PHONY: run-prod
run-prod:
	@docker compose -f docker-compose.prod.external.yml up --build
	@docker compose logs -f

# .PHONY: run-dev
# run-dev:
# 	@docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# 	@docker compose logs -f

