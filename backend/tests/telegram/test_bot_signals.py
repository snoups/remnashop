import asyncio
import contextlib
import json

import pytest
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.bot_signals import RedisBotSignals
from app.core.constants import TRANSLATION_CHANGED_CHANNEL
from app.core.enums import Locale
from app.modules.translations import strip_serializer_escapes
from app.telegram import bot_signals
from app.telegram.bot_signals import listen_for_bot_signals, live_update_handlers
from app.telegram.i18n import build_translator_hub


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
    monkeypatch.setattr(bot_signals, "_RECONNECT_MIN_DELAY_S", 0.01)
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
