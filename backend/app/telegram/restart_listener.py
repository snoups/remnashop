import asyncio
import os
import signal

from loguru import logger
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import TELEGRAM_RESTART_CHANNEL


async def listen_for_restart(config: AppConfig) -> None:
    # Standalone client, not the (nonexistent, in idle mode) DI container --
    # this listener runs in both the idle app and the real one.
    redis = Redis.from_url(config.redis.dsn, decode_responses=True)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(TELEGRAM_RESTART_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            logger.warning(
                "Bot restart requested via dashboard -- exiting for the process "
                "supervisor to restart with fresh settings."
            )
            os.kill(os.getpid(), signal.SIGTERM)
            break
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Restart listener stopped unexpectedly")
        raise
    finally:
        await pubsub.unsubscribe(TELEGRAM_RESTART_CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
