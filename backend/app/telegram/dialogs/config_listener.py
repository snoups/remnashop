import asyncio
from typing import Protocol

from loguru import logger
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import DIALOG_CONFIG_CHANGED_CHANNEL


class _Reloadable(Protocol):
    async def reload(self) -> None: ...


async def listen_for_dialog_config_changes(config: AppConfig, cache: _Reloadable) -> None:
    # Standalone client, not the DI container -- this runs as a background task
    # started once at process startup, outside any request scope.
    redis = Redis.from_url(config.redis.dsn, decode_responses=True)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(DIALOG_CONFIG_CHANGED_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            logger.debug("Dialog config changed, reloading cache")
            await cache.reload()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Dialog config listener stopped unexpectedly")
        raise
    finally:
        await pubsub.unsubscribe(DIALOG_CONFIG_CHANGED_CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
