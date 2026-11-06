import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram_dialog import ShowMode, StartMode
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.bot_signals import RedisBotSignals
from app.core.config import AppConfig
from app.core.constants import (
    PAYMENT_OUTCOME_CHANNEL,
    REDIS_CONNECTION_KWARGS,
    TRANSLATION_CHANGED_CHANNEL,
)
from app.core.enums import Locale, PaymentOutcome
from app.modules.translations import strip_serializer_escapes
from app.telegram import signal_listener
from app.telegram.bot_signals import live_update_handlers, payment_outcome_handlers
from app.telegram.i18n import build_translator_hub
from app.telegram.signal_listener import listen_for_bot_signals
from app.telegram.states import PaymentResult


class _SpyCache:
    def __init__(self) -> None:
        self.reload_count = 0

    async def reload(self) -> None:
        self.reload_count += 1


class _SpyHub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def update_translation(self, locale: str, key: str, value: str) -> bool:
        if key == "broken":
            raise KeyError(key)
        self.calls.append((locale, key, value))
        return True


async def test_listener_routes_each_signal_and_survives_a_failing_handler(redis) -> None:
    cache, hub = _SpyCache(), _SpyHub()
    signals = RedisBotSignals(redis)
    task = asyncio.create_task(listen_for_bot_signals(redis, live_update_handlers(cache, hub)))
    try:
        await asyncio.sleep(0.1)  # let the listener finish subscribing
        await signals.translation_changed(Locale.RU, "broken", "", "x")
        await signals.dialogs_changed()
        await signals.translation_changed(Locale.RU, "msg-main-menu", "", "Привет!")
        for _ in range(50):
            if hub.calls and cache.reload_count:
                break
            await asyncio.sleep(0.05)
        assert cache.reload_count == 1
        assert hub.calls == [("ru", "msg-main-menu", "Привет!")]
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("value", ["line1\nline2\nline3", "", "a\n[glyph](emoji:1)"])
async def test_translation_patch_keeps_multiline_and_empty_values(value: str) -> None:
    hub = build_translator_hub([Locale.EN], {Locale.EN: "msg-a = old\n"}, Locale.EN)
    handlers = live_update_handlers(_SpyCache(), hub)
    await handlers[TRANSLATION_CHANGED_CHANNEL](
        json.dumps({"locale": "en", "message_id": "msg-a", "value": value})
    )
    rendered = hub.get_translator_by_locale("en").get("msg-a")
    assert strip_serializer_escapes(rendered) == value


class _RedisDownOnce:
    """Fails the first subscription the way a Redis restart does."""

    def __init__(self, real: Redis) -> None:
        self._real = real
        self.subscriptions = 0

    def pubsub(self) -> PubSub:
        self.subscriptions += 1
        if self.subscriptions == 1:
            raise RedisConnectionError("Redis is restarting")
        return self._real.pubsub()


async def test_listener_subscribes_again_after_losing_redis(
    redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signal_listener, "_RECONNECT_MIN_DELAY_S", 0.01)
    cache = _SpyCache()
    flaky = _RedisDownOnce(redis)
    task = asyncio.create_task(
        listen_for_bot_signals(flaky, live_update_handlers(cache, _SpyHub()))  # type: ignore[arg-type]
    )
    try:
        for _ in range(50):
            if flaky.subscriptions == 2:
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)  # let the second subscription settle
        await RedisBotSignals(redis).dialogs_changed()
        for _ in range(50):
            if cache.reload_count:
                break
            await asyncio.sleep(0.05)
        assert cache.reload_count == 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class _CountingRedis:
    def __init__(self, real: Redis) -> None:
        self._real = real
        self.subscriptions = 0

    def pubsub(self) -> PubSub:
        self.subscriptions += 1
        return self._real.pubsub()


async def test_listener_keeps_its_subscription_through_a_quiet_spell(
    config: AppConfig,
) -> None:
    # the client times reads out fast; a silent channel must not look like a
    # lost one. Without redis-py's retry, so a dropped read shows here as a
    # second subscription instead of a silent reconnect.
    client = Redis.from_url(
        config.redis.dsn,
        decode_responses=True,
        **{**REDIS_CONNECTION_KWARGS, "socket_timeout": 0.2, "retry_on_timeout": False},
    )
    counting = _CountingRedis(client)
    cache = _SpyCache()
    task = asyncio.create_task(
        listen_for_bot_signals(counting, live_update_handlers(cache, _SpyHub()))  # type: ignore[arg-type]
    )
    try:
        await asyncio.sleep(1.5)
        await RedisBotSignals(client).dialogs_changed()
        for _ in range(50):
            if cache.reload_count:
                break
            await asyncio.sleep(0.05)
        assert cache.reload_count == 1
        assert counting.subscriptions == 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await client.aclose()


@pytest.mark.parametrize(
    ("outcome", "state"),
    [
        (PaymentOutcome.SUCCEEDED, PaymentResult.SUCCESS),
        (PaymentOutcome.NOT_FULFILLED, PaymentResult.FAILED),
        (PaymentOutcome.CANCELED, PaymentResult.CANCELED),
    ],
)
async def test_payment_outcome_handler_starts_window(outcome, state) -> None:
    manager = AsyncMock()
    factory = MagicMock()
    factory.bg.return_value = manager
    bot = MagicMock()
    handler = payment_outcome_handlers(bot, factory)[PAYMENT_OUTCOME_CHANNEL]

    await handler(json.dumps({"telegram_id": 5, "order_id": 7, "outcome": outcome.value}))

    factory.bg.assert_called_once_with(bot=bot, user_id=5, chat_id=5)
    manager.start.assert_awaited_once_with(
        state,
        data={"order_id": 7},
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
