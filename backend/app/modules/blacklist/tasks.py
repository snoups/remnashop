from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.utils.lock import cron_lock
from app.modules.blacklist.dispatch import ReconcileBlacklistDispatch
from app.modules.blacklist.usecases import FetchBlacklistSourcesUseCase
from app.worker.broker import broker

_SYNC_LOCK_TTL_S: Final[int] = 55 * 60


@broker.task(schedule=[{"cron": "0 */6 * * *"}])
@inject(patch_module=True)
async def sync_blacklist_sources_task(
    use_case: FromDishka[FetchBlacklistSourcesUseCase],
    reconcile: FromDishka[ReconcileBlacklistDispatch],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(redis, "blacklist_sync", ttl_seconds=_SYNC_LOCK_TTL_S) as acquired:
        if not acquired:
            return
        await use_case.system()
    await reconcile.kiq()
