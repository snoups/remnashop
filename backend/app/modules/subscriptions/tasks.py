from decimal import Decimal
from typing import Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.enums import Currency, PurchaseType
from app.core.utils.lock import cron_lock
from app.modules.subscriptions.dto import GrantAddOnDto, PlanSnapshot, PurchaseSubscriptionDto
from app.modules.subscriptions.usecases import (
    FulfillPurchaseUseCase,
    GrantAddOnUseCase,
    PruneIdempotencyKeysUseCase,
    ReconcileSubscriptionsUseCase,
)
from app.worker.broker import broker

_RECONCILE_LOCK_TTL_S: Final[int] = 29 * 60


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def purchase_subscription_task(
    user_id: int,
    plan_snapshot: dict,
    duration_days: int,
    price_paid: str,
    currency: str,
    purchase_type: str,
    use_case: FromDishka[FulfillPurchaseUseCase],
    target_subscription_id: Optional[int] = None,
    base_price: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> None:
    await use_case.system(
        PurchaseSubscriptionDto(
            user_id=user_id,
            plan_snapshot=PlanSnapshot.from_json(plan_snapshot),
            duration_days=duration_days,
            price_paid=Decimal(price_paid),
            base_price=Decimal(base_price) if base_price is not None else None,
            currency=Currency(currency),
            purchase_type=PurchaseType(purchase_type),
            target_subscription_id=target_subscription_id,
            idempotency_key=idempotency_key,
            # every queued purchase is a customer's order
            reset_traffic=True,
        )
    )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def grant_addon_task(
    subscription_id: int,
    addon_id: int,
    use_case: FromDishka[GrantAddOnUseCase],
    idempotency_key: Optional[str] = None,
) -> None:
    await use_case.system(
        GrantAddOnDto(
            subscription_id=subscription_id, addon_id=addon_id, idempotency_key=idempotency_key
        )
    )


@broker.task(schedule=[{"cron": "*/30 * * * *"}])
@inject(patch_module=True)
async def reconcile_subscriptions_task(
    use_case: FromDishka[ReconcileSubscriptionsUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(
        redis, "reconcile_subscriptions", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            logger.debug("reconcile_subscriptions_task already running, skipping this tick")
            return
        await use_case.system()


@broker.task(schedule=[{"cron": "15 3 * * *"}])
@inject(patch_module=True)
async def prune_subscription_idempotency_task(
    use_case: FromDishka[PruneIdempotencyKeysUseCase],
) -> None:
    await use_case.system()
