from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PlanType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
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
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    GrantAddOnDto,
    PurchaseSubscriptionDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.tasks import (
    grant_addon_task,
    prune_subscription_idempotency_task,
    purchase_subscription_task,
    run_panel_sync_task,
)
from app.modules.subscriptions.usecases import (
    FulfillPurchaseUseCase,
    GrantAddOnUseCase,
    PurchaseSubscriptionUseCase,
    SyncAllFromPanelUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.settings.factories import SHOP_SETTINGS_FIELDS
from tests.modules.subscriptions.factories import make_plan_snapshot


@pytest.fixture
def fulfill_purchase(
    user_repository: UserRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    uow: UnitOfWork,
) -> FulfillPurchaseUseCase:
    return FulfillPurchaseUseCase(
        user_repository,
        purchase_subscription_use_case,
        TransactionRepository(user_repository.session),
        uow,
    )


def _reconcile_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> SyncAllFromPanelUseCase:
    sync = SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    return SyncAllFromPanelUseCase(
        subscription_repository, remnawave_sdk, sync, uow, redis, event_publisher
    )


def test_purchase_and_grant_tasks_are_retry_enabled() -> None:
    assert purchase_subscription_task.labels.get("retry_on_error") is True
    assert purchase_subscription_task.labels.get("max_retries") == 3
    assert grant_addon_task.labels.get("retry_on_error") is True
    assert grant_addon_task.labels.get("max_retries") == 3


def test_panel_sync_task_is_not_retry_enabled_nor_scheduled() -> None:
    # started by an admin only; a retry would run a second full sync
    assert run_panel_sync_task.labels.get("retry_on_error") is not True
    assert not run_panel_sync_task.labels.get("schedule")


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


async def test_a_free_order_over_the_cap_fails_instead_of_provisioning(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    fulfill_purchase: FulfillPurchaseUseCase,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=444))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="task-free-cap",
            name="task-free-cap",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=1,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=0,
            device_all_reset_enabled=True,
            device_all_reset_cooldown_hours=0,
            link_reset_enabled=True,
            link_reset_cooldown_hours=0,
            fields_set=SHOP_SETTINGS_FIELDS,
        )
    )
    snapshot = make_plan_snapshot(plan_id=plan.id, price_paid=Decimal(0), currency=Currency.RUB)
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=444_000,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://example.com/sub/444000",
            plan_snapshot=snapshot,
        )
    )
    transactions = TransactionRepository(user_repository.session)
    order = await transactions.create(
        CreateTransactionDto(
            user_id=buyer.id,
            plan_id=plan.id,
            plan_snapshot=snapshot,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("500.00"),
            discount_percent=100,
            discount_source=DiscountSource.PURCHASE,
            final_price=Decimal(0),
            anchor_base_price=Decimal("500.00"),
            anchor_final_price=Decimal(0),
            customer_email=None,
            idempotency_key="task-free-cap",
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    await transactions.mark_status(order.id, TransactionStatus.PAID)

    result = await fulfill_purchase.system(
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot,
            duration_days=30,
            price_paid=Decimal(0),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            idempotency_key="task-free-cap",
        )
    )

    assert result is None
    assert len(await subscription_repository.get_active_by_user(buyer.id)) == 1
    assert (await transactions.get_by_id(order.id)).status is TransactionStatus.FAILED
    # the spent 100% purchase discount that made the order free comes back
    assert (await user_repository.find_by_id(buyer.id)).purchase_discount == 100  # type: ignore[union-attr]


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


async def test_sync_from_panel_syncs_status_that_drifted_on_the_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
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

    await _reconcile_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, redis
    ).system()

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.LIMITED


async def test_sync_from_panel_marks_deleted_when_panel_identity_is_gone(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
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
    # not in remnawave_store, so the fake transport 404s (tests/fakes/remnawave.py)

    await _reconcile_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, redis
    ).system()

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.DELETED


async def test_sync_from_panel_skips_subscriptions_already_in_sync(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
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
    )  # _user_payload defaults to "ACTIVE", like created

    await _reconcile_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, redis
    ).system()

    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.ACTIVE


def test_prune_subscription_idempotency_task_carries_a_schedule_label() -> None:
    assert prune_subscription_idempotency_task.labels.get("schedule")


async def test_sync_from_panel_keeps_going_after_one_row_fails_to_sync(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    redis: Redis,
) -> None:
    user = await user_repository.create(CreateUserDto(name="reconcile-iso", telegram_id=91010))
    created = [
        await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=user.id,
                remnawave_user_id=remnawave_user_id,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now() + timedelta(days=30),
                url=f"https://fake-panel.test/sub/{remnawave_user_id}",
                plan_snapshot=make_plan_snapshot(),
            )
        )
        for remnawave_user_id in (91011, 91012)
    ]
    use_case = _reconcile_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, redis
    )
    real_sync = use_case._sync_use_case._execute

    async def sync_failing_first(actor: object, data: SyncSubscriptionStatusDto) -> object:
        if data.remnawave_user_id == 91011:
            raise RuntimeError("boom")
        return await real_sync(actor, data)  # type: ignore[arg-type]

    monkeypatch.setattr(use_case._sync_use_case, "_execute", sync_failing_first)

    await use_case.system()

    refreshed = await subscription_repository.get_by_id(created[1].id)
    assert refreshed.status == SubscriptionStatus.DELETED


async def test_a_delivered_paid_trial_uses_up_the_trial(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    fulfill_purchase: FulfillPurchaseUseCase,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=447))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="paid-trial",
            name="paid-trial",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=Decimal("1.00"))],
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
                plan_id=plan.id, price_paid=Decimal("1.00"), currency=Currency.RUB, is_trial=True
            ),
            duration_days=3,
            price_paid=Decimal("1.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
        )
    )

    assert subscription is not None and subscription.is_trial is True
    reloaded = await user_repository.find_by_id(buyer.id)
    assert reloaded is not None and reloaded.is_trial_available is False
