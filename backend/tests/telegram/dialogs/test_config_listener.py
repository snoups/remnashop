import asyncio
import contextlib

from app.core.config import AppConfig
from app.core.constants import DIALOG_CONFIG_CHANGED_CHANNEL
from app.telegram.dialogs.config_listener import listen_for_dialog_config_changes


class _SpyCache:
    def __init__(self) -> None:
        self.reload_count = 0

    async def reload(self) -> None:
        self.reload_count += 1


async def test_listener_reloads_cache_on_message(config: AppConfig, redis) -> None:
    cache = _SpyCache()
    task = asyncio.create_task(listen_for_dialog_config_changes(config, cache))
    try:
        await asyncio.sleep(0.1)  # let the listener finish subscribing
        await redis.publish(DIALOG_CONFIG_CHANGED_CHANNEL, "changed")
        for _ in range(50):
            if cache.reload_count > 0:
                break
            await asyncio.sleep(0.05)
        assert cache.reload_count == 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
