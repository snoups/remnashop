import asyncio
import json
import os
import signal
from collections.abc import Awaitable, Callable, Mapping
from typing import Final, Protocol

from aiogram import Bot
from aiogram.fsm.state import State
from aiogram_dialog import BgManagerFactory, ShowMode, StartMode
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.constants import (
    DIALOG_CONFIG_CHANGED_CHANNEL,
    PAYMENT_OUTCOME_CHANNEL,
    TELEGRAM_RESTART_CHANNEL,
    TRANSLATION_CHANGED_CHANNEL,
)
from app.core.enums import PaymentOutcome
from app.modules.translations import fluent_value_source
from app.telegram.states import PaymentResult

SignalHandler = Callable[[str], Awaitable[None]]

_RECONNECT_MIN_DELAY_S: Final[float] = 1.0
_RECONNECT_MAX_DELAY_S: Final[float] = 30.0
_POLL_TIMEOUT_S: Final[float] = 1.0
_OUTCOME_STATES: Final[dict[PaymentOutcome, State]] = {
    PaymentOutcome.SUCCEEDED: PaymentResult.SUCCESS,
    PaymentOutcome.NOT_FULFILLED: PaymentResult.FAILED,
    PaymentOutcome.CANCELED: PaymentResult.CANCELED,
}


class _Reloadable(Protocol):
    async def reload(self) -> None: ...


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


def live_update_handlers(cache: _Reloadable, hub: TranslatorHub) -> dict[str, SignalHandler]:
    async def reload_dialogs(_: str) -> None:
        await cache.reload()

    async def patch_translation(data: str) -> None:
        payload = json.loads(data)
        # fluentogram compiles `f"{key} = {value}"`: a raw newline would end the message
        await hub.update_translation(
            payload["locale"], payload["message_id"], fluent_value_source(payload["value"])
        )

    return {
        **restart_handlers(),
        DIALOG_CONFIG_CHANGED_CHANNEL: reload_dialogs,
        TRANSLATION_CHANGED_CHANNEL: patch_translation,
    }


def payment_outcome_handlers(bot: Bot, factory: BgManagerFactory) -> dict[str, SignalHandler]:
    async def show_outcome(data: str) -> None:
        payload = json.loads(data)
        telegram_id = payload["telegram_id"]
        await factory.bg(bot=bot, user_id=telegram_id, chat_id=telegram_id).start(
            _OUTCOME_STATES[PaymentOutcome(payload["outcome"])],
            data={"order_id": payload["order_id"]},
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )

    return {PAYMENT_OUTCOME_CHANNEL: show_outcome}
