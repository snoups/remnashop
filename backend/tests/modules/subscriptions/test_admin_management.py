from datetime import timedelta
from decimal import Decimal

import pytest
from remnapy import RemnawaveSDK
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Locale, PlanType, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    AdminDeleteDeviceDto,
    ChangeSubscriptionPlanDto,
    GrantSubscriptionDto,
    SetSubscriptionEnabledDto,
    SubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    AdminDeleteAllDevicesUseCase,
    AdminDeleteDeviceUseCase,
    AdminListDevicesUseCase,
    AdminReissueSubscriptionUseCase,
    ChangeSubscriptionPlanUseCase,
    GrantSubscriptionUseCase,
    PurchaseSubscriptionUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeHwidStore, FakeUserStore
from tests.modules.subscriptions.factories import make_eligibility

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def _plan(plan_repository: PlanRepository, code: str) -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=code, name=code, type=PlanType.BOTH, traffic_limit=50, device_limit=2
        )
    )
    return await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("300"))],
        )
    )


async def _event_types(session: AsyncSession) -> list[str]:
    return list(
        await session.scalars(select(EventOutboxEntry.event_type).order_by(EventOutboxEntry.id))
    )


@pytest.fixture
def purchase_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )


@pytest.fixture
def grant_use_case(
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    purchase_use_case: PurchaseSubscriptionUseCase,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> GrantSubscriptionUseCase:
    return GrantSubscriptionUseCase(
        user_repository, plan_repository, purchase_use_case, event_publisher, uow
    )


async def _granted(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    telegram_id: int,
    code: str,
    days: int = 40,
) -> SubscriptionDto:
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=telegram_id))
    plan = await _plan(plan_repository, code)
    return await grant_use_case(
        OWNER, GrantSubscriptionDto(user_id=recipient.id, plan_id=plan.id, duration_days=days)
    )


async def test_grant_creates_free_subscription_for_another_user(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9201))
    plan = await _plan(plan_repository, "grant")

    subscription = await grant_use_case(
        OWNER, GrantSubscriptionDto(user_id=recipient.id, plan_id=plan.id, duration_days=10)
    )

    assert subscription.user_id == recipient.id
    assert subscription.plan_snapshot.plan_id == plan.id
    assert subscription.plan_snapshot.price_paid == Decimal(0)
    assert subscription.plan_snapshot.duration_days == 10
    assert subscription.traffic_limit == 50
    expected = datetime_now() + timedelta(days=10)
    assert abs((subscription.expire_at - expected).total_seconds()) < 60
    assert await _event_types(subscription_repository.session) == ["SubscriptionGrantedEvent"]


async def test_grant_ignores_the_active_subscription_cap(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9202))
    plan = await _plan(plan_repository, "capped")
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                max_active_subscriptions=1,
                device_single_reset_enabled=True,
                device_single_reset_cooldown_hours=0,
                device_all_reset_enabled=True,
                device_all_reset_cooldown_hours=0,
                link_reset_enabled=True,
                link_reset_cooldown_hours=0,
            )
        )
    data = GrantSubscriptionDto(user_id=recipient.id, plan_id=plan.id, duration_days=30)

    await grant_use_case(OWNER, data)
    second = await grant_use_case(OWNER, data)

    assert second.user_id == recipient.id


async def test_grant_unknown_user_is_not_found(
    grant_use_case: GrantSubscriptionUseCase, plan_repository: PlanRepository
) -> None:
    plan = await _plan(plan_repository, "nouser")

    with pytest.raises(NotFoundError):
        await grant_use_case(
            OWNER, GrantSubscriptionDto(user_id=999999, plan_id=plan.id, duration_days=30)
        )


async def test_grant_unknown_plan_is_not_found(
    grant_use_case: GrantSubscriptionUseCase, user_repository: UserRepository
) -> None:
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9203))

    with pytest.raises(NotFoundError):
        await grant_use_case(
            OWNER, GrantSubscriptionDto(user_id=recipient.id, plan_id=999999, duration_days=30)
        )


async def test_regular_user_cannot_grant(grant_use_case: GrantSubscriptionUseCase) -> None:
    with pytest.raises(PermissionDeniedError):
        await grant_use_case(
            REGULAR_USER, GrantSubscriptionDto(user_id=1, plan_id=1, duration_days=30)
        )


@pytest.fixture
def change_plan_use_case(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    purchase_use_case: PurchaseSubscriptionUseCase,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> ChangeSubscriptionPlanUseCase:
    return ChangeSubscriptionPlanUseCase(
        subscription_repository,
        user_repository,
        plan_repository,
        purchase_use_case,
        event_publisher,
        uow,
    )


async def test_change_plan_keeping_expiry(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9401, "keep-a")
    new_plan = await _plan(plan_repository, "keep-b")

    changed = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=None),
    )

    assert changed.id != old.id
    assert changed.expire_at == old.expire_at
    assert changed.plan_snapshot.plan_id == new_plan.id
    assert changed.plan_snapshot.price_paid == Decimal(0)
    assert changed.remnawave_user_id == old.remnawave_user_id
    assert (await subscription_repository.get_by_id(old.id)).status is SubscriptionStatus.DELETED
    events = await _event_types(subscription_repository.session)
    assert events[-1] == "SubscriptionPlanChangedByAdminEvent"
    assert "SubscriptionChangedEvent" not in events


async def test_change_plan_with_new_duration(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9402, "dur-a")
    new_plan = await _plan(plan_repository, "dur-b")

    changed = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=5),
    )

    expected = datetime_now() + timedelta(days=5)
    assert abs((changed.expire_at - expected).total_seconds()) < 60
    assert changed.plan_snapshot.duration_days == 5


async def test_change_plan_drops_addons(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    uow: UnitOfWork,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9403, "addon-a")
    addon = await addon_repository.create(
        CreateAddOnDto(name="t10", type=AddOnType.TRAFFIC, amount=10, base_price=Decimal("1"))
    )
    async with uow:
        await subscription_repository.grant_entitlement(
            subscription_id=old.id, addon_id=addon.id, addon_type=addon.type, amount=10
        )
    new_plan = await _plan(plan_repository, "addon-b")

    changed = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=None),
    )

    assert changed.addon_entitlements == []
    assert changed.effective_traffic_limit == new_plan.traffic_limit


async def test_change_plan_of_deleted_subscription_is_rejected(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9404, "del-a")
    async with uow:
        await subscription_repository.mark_deleted(old.id)

    with pytest.raises(ValidationError) as error:
        await change_plan_use_case(
            OWNER,
            ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=1, duration_days=None),
        )
    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED


def _set_enabled(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> SetSubscriptionEnabledUseCase:
    return SetSubscriptionEnabledUseCase(
        subscription_repository,
        remnawave_sdk,
        SubscriptionLifecycleService(subscription_repository),
        event_publisher,
        uow,
    )


async def test_disable_then_enable(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9601, "toggle")
    use_case = _set_enabled(subscription_repository, remnawave_sdk, event_publisher, uow)

    disabled = await use_case(
        OWNER, SetSubscriptionEnabledDto(subscription_id=granted.id, enabled=False)
    )
    assert disabled.status is SubscriptionStatus.DISABLED
    assert remnawave_store[granted.remnawave_user_id]["status"] == "DISABLED"

    enabled = await use_case(
        OWNER, SetSubscriptionEnabledDto(subscription_id=granted.id, enabled=True)
    )
    assert enabled.status is SubscriptionStatus.ACTIVE


async def test_enable_deleted_subscription_is_rejected(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9602, "toggle-del")
    async with uow:
        await subscription_repository.mark_deleted(granted.id)
    use_case = _set_enabled(subscription_repository, remnawave_sdk, event_publisher, uow)

    with pytest.raises(ValidationError):
        await use_case(OWNER, SetSubscriptionEnabledDto(subscription_id=granted.id, enabled=True))


async def test_reset_traffic_zeroes_used_bytes(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9701, "traffic")
    remnawave_store[granted.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] = 12345
    use_case = ResetSubscriptionTrafficUseCase(
        subscription_repository, remnawave_sdk, event_publisher, uow
    )

    await use_case(OWNER, granted.id)

    assert remnawave_store[granted.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] == 0


async def test_admin_reissue_updates_url_without_client_cooldown(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9702, "reissue")
    use_case = AdminReissueSubscriptionUseCase(
        subscription_repository, remnawave_sdk, event_publisher, uow
    )

    reissued = await use_case(OWNER, granted.id)

    assert reissued.url != granted.url
    assert reissued.link_reset_at is None


async def test_reset_traffic_of_deleted_subscription_is_rejected(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9703, "traffic-del")
    async with uow:
        await subscription_repository.mark_deleted(granted.id)
    use_case = ResetSubscriptionTrafficUseCase(
        subscription_repository, remnawave_sdk, event_publisher, uow
    )

    with pytest.raises(ValidationError):
        await use_case(OWNER, granted.id)


def _device(hwid: str, user_id: int) -> dict[str, object]:
    now = datetime_now().isoformat()
    return {
        "hwid": hwid,
        "userId": user_id,
        "platform": "ios",
        "osVersion": None,
        "deviceModel": "iPhone",
        "userAgent": None,
        "requestIp": None,
        "createdAt": now,
        "updatedAt": now,
    }


async def test_admin_device_list_and_delete(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: FakeHwidStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9801, "devices")
    panel_id = granted.remnawave_user_id
    remnawave_hwid_store[panel_id] = [_device(h, panel_id) for h in ("a", "b", "c")]
    list_devices = AdminListDevicesUseCase(subscription_repository, remnawave_sdk, uow)
    delete_one = AdminDeleteDeviceUseCase(
        subscription_repository, remnawave_sdk, event_publisher, uow
    )
    delete_all = AdminDeleteAllDevicesUseCase(
        subscription_repository, remnawave_sdk, event_publisher, uow
    )

    assert [d.hwid for d in await list_devices(OWNER, granted.id)] == ["a", "b", "c"]

    await delete_one(OWNER, AdminDeleteDeviceDto(subscription_id=granted.id, hwid="b"))
    assert [d.hwid for d in await list_devices(OWNER, granted.id)] == ["a", "c"]

    await delete_all(OWNER, granted.id)
    assert await list_devices(OWNER, granted.id) == []
    assert (await subscription_repository.get_by_id(granted.id)).device_all_reset_at is None


async def test_change_plan_of_disabled_subscription_stays_disabled(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9405, "disabled-a")
    await _set_enabled(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, SetSubscriptionEnabledDto(subscription_id=old.id, enabled=False)
    )
    new_plan = await _plan(plan_repository, "disabled-b")

    changed = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=None),
    )

    assert changed.status is SubscriptionStatus.DISABLED
