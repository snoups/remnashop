import asyncio
import contextlib

from app.core.bot_signals import RedisBotSignals
from app.core.enums import Locale
from app.telegram.bot_signals import listen_for_bot_signals, live_update_handlers


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
