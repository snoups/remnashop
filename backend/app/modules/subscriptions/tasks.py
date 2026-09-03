from datetime import timedelta
from decimal import Decimal
from typing import Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType, SubscriptionStatus
from app.core.exceptions import NotFoundError, RemnawavePanelUnavailableError
from app.core.ports import EventPublisher
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    GrantAddOnDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    GrantAddOnUseCase,
    PurchaseSubscriptionUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.users import UserRepository
from app.worker.broker import broker

# Must exceed the longest webhook-resend window of any payment provider --
# deleting a still-resendable key turns a replay into a fresh claim (double
# charge + double provisioning). Re-check against the real provider(s) once
# modules/gateways has a transaction model.
_IDEMPOTENCY_KEY_RETENTION_DAYS: Final[int] = 7
_RECONCILE_LOCK_TTL_S: Final[int] = 29 * 60


async def purchase_subscription(
    *,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    user_repository: UserRepository,
    lifecycle_service: SubscriptionLifecycleService,
    user_id: int,
    plan_snapshot: dict,
    duration_days: int,
    price_paid: str,
    currency: str,
    purchase_type: str,
    target_subscription_id: Optional[int],
    base_price: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> SubscriptionDto:
    actor = await user_repository.get_by_id(user_id)
    if actor is None:
        raise NotFoundError(f"User '{user_id}' not found")

    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        lifecycle_service,
    )
    return await use_case(
        actor,
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
            consumes_purchase_discount=True,
        ),
    )


async def grant_addon(
    *,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    subscription_id: int,
    addon_id: int,
    idempotency_key: Optional[str] = None,
) -> SubscriptionDto:
    use_case = GrantAddOnUseCase(
        subscription_repository, addon_repository, remnawave_sdk, uow, event_publisher
    )
    return await use_case.system(
        GrantAddOnDto(
            subscription_id=subscription_id, addon_id=addon_id, idempotency_key=idempotency_key
        )
    )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def purchase_subscription_task(
    user_id: int,
    plan_snapshot: dict,
    duration_days: int,
    price_paid: str,
    currency: str,
    purchase_type: str,
    subscription_repository: FromDishka[SubscriptionRepository],
    settings_repository: FromDishka[SettingsRepository],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
    user_repository: FromDishka[UserRepository],
    lifecycle_service: FromDishka[SubscriptionLifecycleService],
    target_subscription_id: Optional[int] = None,
    base_price: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> None:
    await purchase_subscription(
        subscription_repository=subscription_repository,
        settings_repository=settings_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        user_repository=user_repository,
        lifecycle_service=lifecycle_service,
        user_id=user_id,
        plan_snapshot=plan_snapshot,
        duration_days=duration_days,
        price_paid=price_paid,
        currency=currency,
        purchase_type=purchase_type,
        target_subscription_id=target_subscription_id,
        base_price=base_price,
        idempotency_key=idempotency_key,
    )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def grant_addon_task(
    subscription_id: int,
    addon_id: int,
    subscription_repository: FromDishka[SubscriptionRepository],
    addon_repository: FromDishka[AddOnRepository],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
    idempotency_key: Optional[str] = None,
) -> None:
    await grant_addon(
        subscription_repository=subscription_repository,
        addon_repository=addon_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        subscription_id=subscription_id,
        addon_id=addon_id,
        idempotency_key=idempotency_key,
    )


async def reconcile_subscriptions(
    *,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    lifecycle_service: SubscriptionLifecycleService,
) -> None:
    # no batching, no concurrency limit -- list_non_terminal() loads
    # every non-terminal row into memory and each panel lookup runs
    # sequentially (reconcile_subscriptions_task's cron_lock only guards
    # against overlapping the *next* run, not this run's own latency). Fine
    # at this project's current scale; upgrade to paginated batches with a
    # bounded gather() (or a panel bulk-list endpoint) if this starts taking
    # close to its own 30-min cron interval.
    sync_use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    for subscription in await subscription_repository.list_non_terminal():
        try:
            panel_user = await remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
        except RemnawaveNotFoundError:
            await sync_use_case.system(
                SyncSubscriptionStatusDto(
                    remnawave_user_id=subscription.remnawave_user_id,
                    status=SubscriptionStatus.DELETED,
                    source="reconcile",
                )
            )
            continue
        except RemnawavePanelUnavailableError:
            logger.warning(
                "Reconcile sweep aborted: Remnawave panel circuit breaker is open; "
                "remaining subscriptions will be picked up by the next scheduled sweep"
            )
            break
        except Exception:  # noqa: BLE001
            logger.exception(
                f"Reconcile sweep failed for subscription '{subscription.id}' "
                f"(remnawave_user_id={subscription.remnawave_user_id}); "
                f"skipping, will retry next sweep"
            )
            continue

        await sync_use_case.system(
            SyncSubscriptionStatusDto(
                remnawave_user_id=subscription.remnawave_user_id,
                status=SubscriptionStatus(panel_user.status),
                source="reconcile",
            )
        )


@broker.task(schedule=[{"cron": "*/30 * * * *"}])
@inject(patch_module=True)
async def reconcile_subscriptions_task(
    subscription_repository: FromDishka[SubscriptionRepository],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
    lifecycle_service: FromDishka[SubscriptionLifecycleService],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(
        redis, "reconcile_subscriptions", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            logger.debug("reconcile_subscriptions_task already running, skipping this tick")
            return
        await reconcile_subscriptions(
            subscription_repository=subscription_repository,
            remnawave_sdk=remnawave_sdk,
            uow=uow,
            event_publisher=event_publisher,
            lifecycle_service=lifecycle_service,
        )


@broker.task(schedule=[{"cron": "15 3 * * *"}])
@inject(patch_module=True)
async def prune_subscription_idempotency_task(
    subscription_repository: FromDishka[SubscriptionRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        cutoff = datetime_now() - timedelta(days=_IDEMPOTENCY_KEY_RETENTION_DAYS)
        (
            purchase_deleted,
            addon_deleted,
        ) = await subscription_repository.delete_stale_idempotency_keys(cutoff)
    logger.info(
        f"Pruned {purchase_deleted} purchase + {addon_deleted} addon idempotency key(s) "
        f"older than {_IDEMPOTENCY_KEY_RETENTION_DAYS}d"
    )
