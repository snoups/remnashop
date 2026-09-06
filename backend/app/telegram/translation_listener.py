import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import TRANSLATION_CHANGED_CHANNEL

if TYPE_CHECKING:
    from fluentogram import TranslatorHub


async def listen_for_translation_changes(config: AppConfig, hub: "TranslatorHub") -> None:
    # Standalone client, not the DI container -- this runs as a background task
    # started once at process startup, outside any request scope. Same shape
    # as app.telegram.dialogs.config_listener.listen_for_dialog_config_changes.
    redis = Redis.from_url(config.redis.dsn, decode_responses=True)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            payload = json.loads(message["data"])
            logger.debug("Translation changed: {}.{}", payload["locale"], payload["message_id"])
            try:
                await hub.update_translation(
                    payload["locale"], payload["message_id"], payload["value"]
                )
            except Exception:
                # One malformed/unexpected message (e.g. a key fluentogram can't
                # hot-patch) must never take the whole listener down -- log and
                # keep consuming.
                logger.warning(
                    "Failed to hot-patch translation {}.{}; skipping",
                    payload.get("locale"),
                    payload.get("message_id"),
                )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Translation change listener stopped unexpectedly")
        raise
    finally:
        await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
