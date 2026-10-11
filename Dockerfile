FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS frontend-builder
WORKDIR /opt/frontend
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-alpine@sha256:7fb7cdfb345b596cf096f713fafb78fd814bb594a0d4136d32f6fdcc73ad5a00 AS backend-builder
WORKDIR /opt/remnashop
ARG UV_EXTRA=""
COPY backend/pyproject.toml backend/uv.lock ./
RUN if [ -n "$UV_EXTRA" ]; then \
        uv sync --locked --no-dev --compile-bytecode --extra "$UV_EXTRA"; \
    else \
        uv sync --locked --no-dev --compile-bytecode; \
    fi \
    && rm -rf .venv/lib/python3.12/site-packages/pip* \
              .venv/lib/python3.12/site-packages/setuptools* \
              .venv/lib/python3.12/site-packages/wheel*

FROM python:3.12-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 AS final
WORKDIR /opt/remnashop

ARG BUILD_TIME
ARG BUILD_BRANCH
ARG BUILD_COMMIT
ARG BUILD_TAG
ENV BUILD_TIME=${BUILD_TIME} \
    BUILD_BRANCH=${BUILD_BRANCH} \
    BUILD_COMMIT=${BUILD_COMMIT} \
    BUILD_TAG=${BUILD_TAG}

RUN apk add --no-cache postgresql-client
ENV PATH="/opt/remnashop/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --from=backend-builder /opt/remnashop/.venv ./.venv
COPY backend/app ./app
COPY backend/assets ./assets
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend-builder /opt/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh ./
RUN chmod +x ./docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
