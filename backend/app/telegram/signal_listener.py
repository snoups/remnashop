import asyncio
import os
import signal
from collections.abc import Awaitable, Callable, Mapping
from typing import Final

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.constants import TELEGRAM_RESTART_CHANNEL

# no aiogram here: the idle app (no bot token yet) listens for a restart only
SignalHandler = Callable[[str], Awaitable[None]]

_RECONNECT_MIN_DELAY_S: Final[float] = 1.0
_RECONNECT_MAX_DELAY_S: Final[float] = 30.0
_POLL_TIMEOUT_S: Final[float] = 1.0


async def listen_for_bot_signals(redis: Redis, handlers: Mapping[str, SignalHandler]) -> None:
    # the receiving end of app.core.bot_signals; one subscription for every channel
    delay = _RECONNECT_MIN_DELAY_S
    while True:
        try:
            async with redis.pubsub() as pubsub:
                await pubsub.subscribe(*handlers)
                delay = _RECONNECT_MIN_DELAY_S
                while True:
                    # an explicit read timeout: listen() would wait under the
                    # client's socket_timeout and drop the subscription when idle
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=_POLL_TIMEOUT_S
                    )
                    if message is None or message["type"] != "message":
                        continue
                    channel = message["channel"]
                    try:
                        await handlers[channel](message["data"])
                    except Exception:
                        # one bad message must not stop the bot picking up the next one
                        logger.exception(f"Bot signal on '{channel}' failed; still listening")
        except (RedisConnectionError, RedisTimeoutError, OSError) as error:
            # outlasted redis-py's retries: subscribe again once Redis is back
            logger.warning(f"Bot signal subscription lost ({error}); retrying in {delay}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY_S)


async def _restart(_: str) -> None:
    # exit for the process supervisor to bring the bot back with fresh settings
    logger.warning("Bot restart requested via dashboard -- exiting for the supervisor to restart")
    os.kill(os.getpid(), signal.SIGTERM)


def restart_handlers() -> dict[str, SignalHandler]:
    return {TELEGRAM_RESTART_CHANNEL: _restart}
