from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.utils.lock import cron_lock
from app.modules.promocodes.usecases import WarnExpiringPromocodeDiscountsUseCase
from app.worker.broker import broker

_WARN_LOCK_TTL_S: Final[int] = 10 * 60


@broker.task(schedule=[{"cron": "20 * * * *"}])
@inject(patch_module=True)
async def warn_expiring_promocode_discounts_task(
    use_case: FromDishka[WarnExpiringPromocodeDiscountsUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(
        redis, "promocode_discount_warning", ttl_seconds=_WARN_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            return
        await use_case.system()
