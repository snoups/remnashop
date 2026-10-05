from typing import Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.utils.lock import cron_lock
from app.modules.loyalty.dto import RecalculateLoyaltyDto
from app.modules.loyalty.usecases import RecalculateLoyaltyDiscountsUseCase
from app.worker.broker import broker

_FULL_RUN_LOCK_TTL_S: Final[int] = 55 * 60
_RERUN_KEY: Final[str] = f"{REDIS_KEY_PREFIX}loyalty_recalc_rerun"


@broker.task(schedule=[{"cron": "0 3 * * *"}])
@inject(patch_module=True)
async def recalculate_loyalty_discounts_task(
    use_case: FromDishka[RecalculateLoyaltyDiscountsUseCase],
    redis: FromDishka[Redis],
    user_ids: Optional[list[int]] = None,
) -> None:
    if user_ids is not None:
        await use_case.system(RecalculateLoyaltyDto(user_ids=user_ids))
        return
    async with cron_lock(redis, "loyalty_recalc", ttl_seconds=_FULL_RUN_LOCK_TTL_S) as acquired:
        if not acquired:
            # the running pass may have read settings older than this request's
            await redis.set(_RERUN_KEY, "1", ex=_FULL_RUN_LOCK_TTL_S)
            return
        await use_case.system(RecalculateLoyaltyDto())
    # checked after the lock is released: a request blocked before that has left its mark,
    # one arriving after takes the lock itself
    if await redis.getdel(_RERUN_KEY):
        await recalculate_loyalty_discounts_task.kiq()  # type: ignore[call-overload]
