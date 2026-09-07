import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.__version__ import __version__
from app.core.config import AppConfig
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.telegram.restart_listener import listen_for_restart


def get_idle_app(config: AppConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Standalone client, not a DI container -- the idle app has none.
        redis = Redis.from_url(config.redis.dsn, decode_responses=True)
        restart_task = asyncio.create_task(listen_for_restart(config))
        runtime_heartbeat_task = asyncio.create_task(poll_runtime_heartbeat(redis, "telegram"))
        yield
        runtime_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime_heartbeat_task
        restart_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await restart_task
        await redis.aclose()

    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop Telegram Webhook (idle)",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "waiting_for_bot_token"}

    return app
