from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Currency, PlanType, PurchaseType, SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    GrantAddOnDto,
    PurchaseSubscriptionDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.tasks import (
    grant_addon_task,
    prune_subscription_idempotency_task,
    purchase_subscription_task,
    reconcile_subscriptions_task,
)
from app.modules.subscriptions.usecases import (
    FulfillPurchaseUseCase,
    GrantAddOnUseCase,
    PurchaseSubscriptionUseCase,
    ReconcileSubscriptionsUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import make_plan_snapshot


@pytest.fixture
def fulfill_purchase(
    user_repository: UserRepository, purchase_subscription_use_case: PurchaseSubscriptionUseCase
) -> FulfillPurchaseUseCase:
    return FulfillPurchaseUseCase(user_repository, purchase_subscription_use_case)


def _reconcile_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> ReconcileSubscriptionsUseCase:
    sync = SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    return ReconcileSubscriptionsUseCase(subscription_repository, remnawave_sdk, sync)


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
    fulfill_purchase: FulfillPurchaseUseCase,
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
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    subscription = await fulfill_purchase.system(
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=make_plan_snapshot(
                plan_id=plan.id, price_paid=Decimal("299.00"), currency=Currency.RUB
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
        )
    )

    assert subscription.user_id == buyer.id


async def test_purchase_subscription_task_body_provisions_a_paid_order_past_the_cap(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    fulfill_purchase: FulfillPurchaseUseCase,
) -> None:
    # The cap is enforced at checkout; once the customer has paid, the order
    # is honoured even if the cap filled up in the meantime.
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=443))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="task-cap",
            name="task-cap",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    for attempt in range(4):
        await fulfill_purchase.system(
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=make_plan_snapshot(
                    plan_id=plan.id, price_paid=Decimal("299.00"), currency=Currency.RUB
                ),
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                idempotency_key=f"task-cap-{attempt}",
            )
        )

    assert len(await subscription_repository.get_active_by_user(buyer.id)) == 4


async def test_grant_addon_task_body_grants_an_entitlement(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    fulfill_purchase: FulfillPurchaseUseCase,
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
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    subscription = await fulfill_purchase.system(
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=make_plan_snapshot(
                plan_id=plan.id, price_paid=Decimal("299.00"), currency=Currency.RUB
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
        )
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="task-addon", type=AddOnType.TRAFFIC, amount=25, base_price=Decimal("1.99")
        )
    )

    granted = await GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    ).system(GrantAddOnDto(subscription_id=subscription.id, addon_id=addon.id))

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

    await _reconcile_use_case(subscription_repository, remnawave_sdk, uow, event_publisher).system()

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

    await _reconcile_use_case(subscription_repository, remnawave_sdk, uow, event_publisher).system()

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

    await _reconcile_use_case(subscription_repository, remnawave_sdk, uow, event_publisher).system()

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.ACTIVE


def test_prune_subscription_idempotency_task_carries_a_schedule_label() -> None:
    assert prune_subscription_idempotency_task.labels.get("schedule")
