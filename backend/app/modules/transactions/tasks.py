from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.utils.lock import cron_lock
from app.modules.transactions.dto import ReconcilePaidTransactionsDto
from app.modules.transactions.usecases import (
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
)
from app.worker.broker import broker

_RECONCILE_LOCK_TTL_S: Final[int] = 14 * 60


@broker.task(schedule=[{"cron": "*/10 * * * *"}])
@inject(patch_module=True)
async def prune_expired_transactions_task(
    use_case: FromDishka[PruneExpiredTransactionsUseCase],
) -> None:
    await use_case.system()


@broker.task(schedule=[{"cron": "*/15 * * * *"}])
@inject(patch_module=True)
async def reconcile_paid_transactions_task(
    use_case: FromDishka[ReconcilePaidTransactionsUseCase],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(
        redis, "reconcile_paid_transactions", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            logger.debug("reconcile_paid_transactions_task already running, skipping this tick")
            return
        await use_case.system(ReconcilePaidTransactionsDto())
