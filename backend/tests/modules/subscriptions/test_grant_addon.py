from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK
from sqlalchemy import select

from app.core.constants import GB_TO_BYTES
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    Locale,
    PlanType,
    PurchaseType,
    Role,
    SubscriptionStatus,
)
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    RemnawavePanelUnavailableError,
)
from app.core.ports import EventPublisher
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
from app.modules.pricing.repository import PricingRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    GrantAddOnDto,
    PurchaseSubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import GrantAddOnUseCase, PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore
from tests.modules.subscriptions.factories import make_eligibility, snapshot_from_plan

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


async def _create_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    telegram_id: int,
) -> tuple[UserDto, int]:
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=f"gp{telegram_id}",
            name=f"gp{telegram_id}",
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
    plan = await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
        UserRepository(subscription_repository.session),
    )
    subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(plan, price_paid=Decimal("299.00")),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    return buyer, subscription.id


async def test_system_can_grant_addon_and_push_limit_to_panel(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    _, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        431,
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="traffic-50gb", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal("1.99")
        )
    )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    granted = await use_case.system(
        GrantAddOnDto(subscription_id=subscription_id, addon_id=addon.id)
    )

    assert granted.effective_traffic_limit == 150
    assert len(granted.addon_entitlements) == 1
    # Wire-level check: a TRAFFIC grant must never send an explicit null
    # hwid_device_limit to the panel.
    panel_payload = remnawave_store[granted.remnawave_user_id]
    assert panel_payload["trafficLimitBytes"] == 150 * GB_TO_BYTES
    assert panel_payload["hwidDeviceLimit"] == 3  # unchanged, base plan value


async def test_grant_addon_event_records_subscription_owner_as_target(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        436,
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="traffic-10gb", type=AddOnType.TRAFFIC, amount=10, base_price=Decimal("0.99")
        )
    )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case.system(GrantAddOnDto(subscription_id=subscription_id, addon_id=addon.id))

    row = (
        await subscription_repository.session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "SubscriptionAddOnGrantedEvent"
            )
        )
    ).one()
    assert row.payload["target"]["id"] == buyer.id
    assert row.payload["target"]["telegram_id"] == 436
    assert row.payload["addon_type"] == addon.type


async def test_real_actor_cannot_call_grant_addon_directly(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    _, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        432,
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="traffic-50gb-2", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal("1.99")
        )
    )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(OWNER, GrantAddOnDto(subscription_id=subscription_id, addon_id=addon.id))


async def test_grant_addon_unknown_addon_raises_not_found(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    _, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        433,
    )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(NotFoundError):
        await use_case.system(GrantAddOnDto(subscription_id=subscription_id, addon_id=999_999))


async def test_grant_addon_retried_after_panel_failure_does_not_double_grant(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        435,
    )
    # committed, as in production: the failed attempt rolls its own transaction back
    async with uow:
        addon = await addon_repository.create(
            CreateAddOnDto(
                name="traffic-50gb-retry",
                type=AddOnType.TRAFFIC,
                amount=50,
                base_price=Decimal("1.99"),
            )
        )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    calls = {"n": 0}
    real_update_user = remnawave_sdk.users.update_user

    async def flaky_update_user(request: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RemnawavePanelUnavailableError("panel down")
        return await real_update_user(request)

    monkeypatch.setattr(remnawave_sdk.users, "update_user", flaky_update_user)

    grant_dto = GrantAddOnDto(
        subscription_id=subscription_id, addon_id=addon.id, idempotency_key="retry-key-1"
    )

    with pytest.raises(RemnawavePanelUnavailableError):
        await use_case.system(grant_dto)

    # Force the retry's idempotency-key lookup to round-trip to Postgres rather
    # than resolve against the session identity map.
    subscription_repository.session.expunge_all()
    granted = await use_case.system(grant_dto)

    assert calls["n"] == 2
    assert [e for e in granted.addon_entitlements if e.addon_id == addon.id] != []
    assert len(granted.addon_entitlements) == 1
    assert granted.effective_traffic_limit == 150


async def test_system_can_grant_devices_addon_without_clearing_traffic_limit(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    _, subscription_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        434,
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="devices-addon", type=AddOnType.DEVICES, amount=2, base_price=Decimal("0.99")
        )
    )
    use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    granted = await use_case.system(
        GrantAddOnDto(subscription_id=subscription_id, addon_id=addon.id)
    )

    assert granted.effective_device_limit == 5  # 3 base + 2 addon
    assert granted.effective_traffic_limit == 100  # unchanged, base plan value
    # a DEVICES grant must not send traffic_limit_bytes=null: exclude_unset
    # keeps a field passed as None
    panel_payload = remnawave_store[granted.remnawave_user_id]
    assert panel_payload["trafficLimitBytes"] == 100 * GB_TO_BYTES
    assert panel_payload["hwidDeviceLimit"] == 5


async def _grant_use_case(
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> GrantAddOnUseCase:
    return GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )


async def test_an_addon_for_a_replaced_subscription_lands_on_its_successor(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer, replaced_id = await _create_subscription(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        441,
    )
    replaced = await subscription_repository.get_by_id(replaced_id)
    # a plan change after the promocode was activated: same panel user, bigger plan
    async with uow:
        await subscription_repository.mark_deleted(replaced_id)
        successor = await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=buyer.id,
                remnawave_user_id=replaced.remnawave_user_id,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=500,
                device_limit=3,
                expire_at=replaced.expire_at,
                url=replaced.url,
                plan_snapshot=replaced.plan_snapshot,
            )
        )
        addon = await addon_repository.create(
            CreateAddOnDto(
                name="traffic-50gb-late", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal(1)
            )
        )
    use_case = await _grant_use_case(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    granted = await use_case.system(GrantAddOnDto(subscription_id=replaced_id, addon_id=addon.id))

    assert granted.id == successor.id
    assert granted.effective_traffic_limit == 550
    assert remnawave_store[replaced.remnawave_user_id]["trafficLimitBytes"] == 550 * GB_TO_BYTES
    assert (await subscription_repository.get_by_id(replaced_id)).addon_entitlements == []
