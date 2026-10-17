from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.broker import broker
from app.core.utils.lock import cron_lock
from app.modules.announcements.usecases import SyncAnnouncementsUseCase

_SYNC_INTERVAL_S: Final[int] = 30 * 60
_SYNC_LOCK_TTL_S: Final[int] = 25 * 60


# interval, not cron: taskiq fires an interval schedule as soon as the scheduler
# starts, so a freshly updated panel has its "what's new" before the first login
@broker.task(schedule=[{"interval": _SYNC_INTERVAL_S}])
@inject(patch_module=True)
async def sync_announcements_task(
    use_case: FromDishka[SyncAnnouncementsUseCase],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(redis, "announcements_sync", ttl_seconds=_SYNC_LOCK_TTL_S) as acquired:
        if not acquired:
            return
        await use_case.system()
