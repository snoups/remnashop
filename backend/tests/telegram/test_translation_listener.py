import asyncio
import contextlib

from app.core.config import AppConfig
from app.core.enums import Locale
from app.modules.translations import publish_translation_change
from app.telegram.translation_listener import listen_for_translation_changes


class _SpyHub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def update_translation(self, locale: str, key: str, value: str) -> bool:
        self.calls.append((locale, key, value))
        return True


async def test_listener_patches_hub_on_message(config: AppConfig, redis) -> None:
    hub = _SpyHub()
    task = asyncio.create_task(listen_for_translation_changes(config, hub))
    try:
        await asyncio.sleep(0.1)  # let the listener finish subscribing
        await publish_translation_change(
            redis, Locale.RU, "msg-main-menu", "Привет, { $name }!", attribute_id=""
        )
        for _ in range(50):
            if hub.calls:
                break
            await asyncio.sleep(0.05)
        assert hub.calls == [("ru", "msg-main-menu", "Привет, { $name }!")]
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
