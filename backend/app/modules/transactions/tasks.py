from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError

from app.core.broker import broker
from app.core.exceptions import RetryableTaskError
from app.core.utils.lock import cron_lock
from app.modules.transactions.dto import ReconcilePaidTransactionsDto, StarsPaymentDto
from app.modules.transactions.usecases import (
    ConfirmStarsPaymentUseCase,
    NotifyPaymentWaitlistUseCase,
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
)

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


@broker.task
@inject(patch_module=True)
async def notify_payment_waitlist_task(
    use_case: FromDishka[NotifyPaymentWaitlistUseCase],
) -> None:
    await use_case.system()


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def confirm_stars_payment_task(
    telegram_id: int,
    payload: str,
    currency: str,
    total_amount: int,
    charge_id: str,
    use_case: FromDishka[ConfirmStarsPaymentUseCase],
) -> None:
    try:
        await use_case.system(
            StarsPaymentDto(
                telegram_id=telegram_id,
                payload=payload,
                currency=currency,
                total_amount=total_amount,
                charge_id=charge_id,
            )
        )
    except (SQLAlchemyError, OSError) as error:
        # the transaction rolled back and the PAID transition is conditional,
        # so a repeat settles the order at most once
        raise RetryableTaskError(f"Stars payment '{charge_id}' not settled yet") from error
