from datetime import timedelta
from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import DiscountSource
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.subscriptions import (
    IDEMPOTENCY_KEY_RETENTION_DAYS,
    SubscriptionRepository,
    purchase_subscription_task,
)
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository
from app.worker.broker import broker

# Grace period between an order becoming PAID and this sweep considering it
# stuck -- gives the normal async .kiq() dispatch + worker run time to
# complete before we second-guess it.
_RECONCILIATION_GRACE_PERIOD: Final[timedelta] = timedelta(minutes=10)
_RECONCILE_LOCK_TTL_S: Final[int] = 14 * 60
# Must stay inside the idempotency-key retention: past it, a key-less order
# looks unprovisioned and a redispatch would provision it a second time.
_RECONCILIATION_WINDOW: Final[timedelta] = timedelta(days=IDEMPOTENCY_KEY_RETENTION_DAYS - 1)


async def prune_expired_transactions(
    *,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        canceled = await transaction_repository.cancel_expired_pending(datetime_now())
        # the one-shot discount was spent when the order was created; an order
        # nobody paid gives it back
        for order in canceled:
            if order.discount_source is DiscountSource.PURCHASE:
                await user_repository.restore_purchase_discount(
                    order.user_id, order.discount_percent, order.discount_promocode_id
                )
    logger.info(f"Canceled {len(canceled)} unpaid transaction(s) past their expiry")


@broker.task(schedule=[{"cron": "*/10 * * * *"}])
@inject(patch_module=True)
async def prune_expired_transactions_task(
    transaction_repository: FromDishka[TransactionRepository],
    user_repository: FromDishka[UserRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    await prune_expired_transactions(
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
    )


async def reconcile_paid_transactions(
    *,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    grace_period: timedelta = _RECONCILIATION_GRACE_PERIOD,
) -> None:
    now = datetime_now()
    stuck = await transaction_repository.list_paid_awaiting_reconciliation(
        now - grace_period, since=now - _RECONCILIATION_WINDOW
    )

    redispatched = 0
    for order in stuck:
        existing = await subscription_repository.get_subscription_by_idempotency_key(
            order.idempotency_key
        )
        if existing is not None:
            async with uow:
                await transaction_repository.mark_fulfilled(order.id)
            continue

        # Same idempotency_key as the original attempt -- safe to redispatch
        # even if that attempt is still in flight or actually succeeded
        # (claim_idempotency_key/get_subscription_by_idempotency_key already
        # guard against a double-provision).
        await purchase_subscription_task.kiq(  # type: ignore[call-overload]
            user_id=order.user_id,
            plan_snapshot=order.plan_snapshot.to_json(),
            duration_days=order.duration_days,
            price_paid=str(order.final_price),
            currency=order.currency.value,
            purchase_type=order.purchase_type.value,
            target_subscription_id=order.target_subscription_id,
            idempotency_key=order.idempotency_key,
            base_price=str(order.base_price),
        )
        redispatched += 1

    logger.info(
        f"Reconciliation sweep: {redispatched} of {len(stuck)} stuck PAID transaction(s) "
        f"redispatched"
    )


@broker.task(schedule=[{"cron": "*/15 * * * *"}])
@inject(patch_module=True)
async def reconcile_paid_transactions_task(
    transaction_repository: FromDishka[TransactionRepository],
    subscription_repository: FromDishka[SubscriptionRepository],
    uow: FromDishka[UnitOfWork],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(
        redis, "reconcile_paid_transactions", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            logger.debug("reconcile_paid_transactions_task already running, skipping this tick")
            return
        await reconcile_paid_transactions(
            transaction_repository=transaction_repository,
            subscription_repository=subscription_repository,
            uow=uow,
        )
