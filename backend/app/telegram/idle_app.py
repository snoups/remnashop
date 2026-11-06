import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import REDIS_CONNECTION_KWARGS
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.telegram.signal_listener import listen_for_bot_signals, restart_handlers


def get_idle_app(config: AppConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # standalone client, the idle app has no DI container
        redis = Redis.from_url(config.redis.dsn, decode_responses=True, **REDIS_CONNECTION_KWARGS)
        restart_task = asyncio.create_task(listen_for_bot_signals(redis, restart_handlers()))
        runtime_heartbeat_task = asyncio.create_task(
            poll_runtime_heartbeat(redis, "telegram", config.instance_name)
        )
        yield
        runtime_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime_heartbeat_task
        restart_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await restart_task
        await redis.aclose()

    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop Telegram Webhook (idle)",
        version=config.build.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "waiting_for_bot_token"}

    return app
