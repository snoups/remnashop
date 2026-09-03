from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Currency, PlanType, PurchaseType, SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import CreateAddOnDto, CreateSubscriptionDto
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.tasks import (
    grant_addon,
    grant_addon_task,
    prune_subscription_idempotency_task,
    purchase_subscription,
    purchase_subscription_task,
    reconcile_subscriptions,
    reconcile_subscriptions_task,
)
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import make_plan_snapshot


def test_purchase_and_grant_tasks_are_retry_enabled() -> None:
    assert purchase_subscription_task.labels.get("retry_on_error") is True
    assert purchase_subscription_task.labels.get("max_retries") == 3
    assert grant_addon_task.labels.get("retry_on_error") is True
    assert grant_addon_task.labels.get("max_retries") == 3


def test_reconcile_task_is_not_retry_enabled() -> None:
    assert reconcile_subscriptions_task.labels.get("retry_on_error") is not True


async def test_purchase_subscription_task_body_creates_a_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=441))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="task1",
            name="task1",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    subscription = await purchase_subscription(
        subscription_repository=subscription_repository,
        settings_repository=settings_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        user_repository=user_repository,
        lifecycle_service=SubscriptionLifecycleService(subscription_repository),
        user_id=buyer.id,
        plan_snapshot=make_plan_snapshot(
            plan_id=plan.id, price_paid=Decimal("299.00"), currency=Currency.RUB
        ).to_json(),
        duration_days=30,
        price_paid="299.00",
        currency=Currency.RUB.value,
        purchase_type=PurchaseType.NEW.value,
        target_subscription_id=None,
    )

    assert subscription.user_id == buyer.id


async def test_grant_addon_task_body_grants_an_entitlement(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=442))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="task2",
            name="task2",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    subscription = await purchase_subscription(
        subscription_repository=subscription_repository,
        settings_repository=settings_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        user_repository=user_repository,
        lifecycle_service=SubscriptionLifecycleService(subscription_repository),
        user_id=buyer.id,
        plan_snapshot=make_plan_snapshot(
            plan_id=plan.id, price_paid=Decimal("299.00"), currency=Currency.RUB
        ).to_json(),
        duration_days=30,
        price_paid="299.00",
        currency=Currency.RUB.value,
        purchase_type=PurchaseType.NEW.value,
        target_subscription_id=None,
    )
    addon = await addon_repository.create(
        CreateAddOnDto(name="task-addon", type=AddOnType.TRAFFIC, amount=25)
    )

    granted = await grant_addon(
        subscription_repository=subscription_repository,
        addon_repository=addon_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        subscription_id=subscription.id,
        addon_id=addon.id,
    )

    assert granted.effective_traffic_limit == 125


async def test_reconcile_syncs_status_that_drifted_on_the_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="reconcile1", telegram_id=91001))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=91001,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://fake-panel.test/sub/91001",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    payload = _user_payload(
        user_id=91001, username="rs_test_91001", expire_at=datetime_now() + timedelta(days=30)
    )
    payload["status"] = "LIMITED"
    remnawave_store[91001] = payload

    await reconcile_subscriptions(
        subscription_repository=subscription_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        lifecycle_service=SubscriptionLifecycleService(subscription_repository),
    )

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.LIMITED


async def test_reconcile_marks_deleted_when_panel_identity_is_gone(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="reconcile2", telegram_id=91002))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=91002,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://fake-panel.test/sub/91002",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    # Deliberately not added to remnawave_store -- the fake transport 404s
    # any user id it doesn't know about (see tests/fakes/remnawave.py).

    await reconcile_subscriptions(
        subscription_repository=subscription_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        lifecycle_service=SubscriptionLifecycleService(subscription_repository),
    )

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.DELETED


async def test_reconcile_skips_subscriptions_already_in_sync(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="reconcile3", telegram_id=91003))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=91003,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://fake-panel.test/sub/91003",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    remnawave_store[91003] = _user_payload(
        user_id=91003, username="rs_test_91003", expire_at=datetime_now() + timedelta(days=30)
    )  # _user_payload's own default status is already "ACTIVE" -- matches created's status

    await reconcile_subscriptions(
        subscription_repository=subscription_repository,
        remnawave_sdk=remnawave_sdk,
        uow=uow,
        event_publisher=event_publisher,
        lifecycle_service=SubscriptionLifecycleService(subscription_repository),
    )

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.ACTIVE


def test_prune_subscription_idempotency_task_carries_a_schedule_label() -> None:
    assert prune_subscription_idempotency_task.labels.get("schedule")
