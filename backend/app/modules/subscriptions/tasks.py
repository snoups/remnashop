from decimal import Decimal
from typing import Optional

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType, SubscriptionStatus
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.modules.plans import PlanRepository
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    GrantAddOnDto,
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


async def purchase_subscription(
    *,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    user_repository: UserRepository,
    lifecycle_service: SubscriptionLifecycleService,
    user_id: int,
    plan_id: int,
    duration_days: int,
    price_paid: str,
    currency: str,
    purchase_type: str,
    target_subscription_id: Optional[int],
) -> SubscriptionDto:
    actor = await user_repository.get_by_id(user_id)
    if actor is None:
        raise NotFoundError(f"User '{user_id}' not found")

    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        lifecycle_service,
    )
    return await use_case(
        actor,
        PurchaseSubscriptionDto(
            user_id=user_id,
            plan_id=plan_id,
            duration_days=duration_days,
            price_paid=Decimal(price_paid),
            currency=Currency(currency),
            purchase_type=PurchaseType(purchase_type),
            target_subscription_id=target_subscription_id,
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
) -> SubscriptionDto:
    use_case = GrantAddOnUseCase(
        subscription_repository, addon_repository, remnawave_sdk, uow, event_publisher
    )
    return await use_case.system(GrantAddOnDto(subscription_id=subscription_id, addon_id=addon_id))


@broker.task
@inject(patch_module=True)
async def purchase_subscription_task(
    user_id: int,
    plan_id: int,
    duration_days: int,
    price_paid: str,
    currency: str,
    purchase_type: str,
    plan_repository: FromDishka[PlanRepository],
    subscription_repository: FromDishka[SubscriptionRepository],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
    user_repository: FromDishka[UserRepository],
    lifecycle_service: FromDishka[SubscriptionLifecycleService],
    target_subscription_id: Optional[int] = None,
) -> None:
    await purchase_subscription(
        plan_repository=plan_repository,
        subscription_repository=subscription_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        user_repository=user_repository,
        lifecycle_service=lifecycle_service,
        user_id=user_id,
        plan_id=plan_id,
        duration_days=duration_days,
        price_paid=price_paid,
        currency=currency,
        purchase_type=purchase_type,
        target_subscription_id=target_subscription_id,
    )


@broker.task
@inject(patch_module=True)
async def grant_addon_task(
    subscription_id: int,
    addon_id: int,
    subscription_repository: FromDishka[SubscriptionRepository],
    addon_repository: FromDishka[AddOnRepository],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
) -> None:
    await grant_addon(
        subscription_repository=subscription_repository,
        addon_repository=addon_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        subscription_id=subscription_id,
        addon_id=addon_id,
    )


async def reconcile_subscriptions(
    *,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    lifecycle_service: SubscriptionLifecycleService,
) -> None:
    # No batching, no concurrency limit, no overlap-guard against the next
    # scheduled run: list_non_terminal() loads every non-terminal row into
    # memory and each panel lookup runs sequentially. Fine at this project's
    # current scale; if a sweep starts taking close to its own 30-min cron
    # interval, upgrade to paginated batches with a bounded gather() (or a
    # panel bulk-list endpoint) before it starts overlapping the next run.
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
) -> None:
    await reconcile_subscriptions(
        subscription_repository=subscription_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        lifecycle_service=lifecycle_service,
    )
