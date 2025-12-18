FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /opt/remnashop

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-cache --compile-bytecode \
    && find .venv -type d -name "__pycache__" -exec rm -rf {} + \
    && rm -rf .venv/lib/python3.12/site-packages/pip* \
    && rm -rf .venv/lib/python3.12/site-packages/setuptools* \
    && rm -rf .venv/lib/python3.12/site-packages/wheel*

FROM python:3.12-alpine AS final

WORKDIR /opt/remnashop

ARG BUILD_TIME
ARG BUILD_BRANCH
ARG BUILD_COMMIT
ARG BUILD_TAG

ENV BUILD_TIME=${BUILD_TIME}
ENV BUILD_BRANCH=${BUILD_BRANCH}
ENV BUILD_COMMIT=${BUILD_COMMIT}
ENV BUILD_TAG=${BUILD_TAG}

COPY --from=builder /opt/remnashop/.venv /opt/remnashop/.venv

ENV PATH="/opt/remnashop/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/remnashop

COPY ./src ./src
COPY ./assets /opt/remnashop/assets.default
COPY ./docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
