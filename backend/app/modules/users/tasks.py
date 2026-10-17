from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.broker import broker
from app.core.utils.lock import cron_lock
from app.modules.users.usecases import BlockBlacklistMatchesUseCase

_RECONCILE_LOCK_TTL_S: Final[int] = 10 * 60


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def reconcile_blacklist_task(
    use_case: FromDishka[BlockBlacklistMatchesUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(
        redis, "blacklist_reconcile", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            return
        await use_case.system()
