from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Locale, PlanType, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    RemnawavePanelUnavailableError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
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
from app.modules.settings.dto import UpdateBotRequirementsDto, UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    AdminDeleteDeviceDto,
    ChangeSubscriptionPlanDto,
    ChannelMembershipDto,
    GrantSubscriptionDto,
    ListSubscriptionsDto,
    SetSubscriptionEnabledDto,
    SubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.usage import PanelTrafficUsage
from app.modules.subscriptions.usecases import (
    AdminDeleteAllDevicesUseCase,
    AdminDeleteDeviceUseCase,
    AdminListDevicesUseCase,
    AdminReissueSubscriptionUseCase,
    ApplyChannelMembershipUseCase,
    ChangeSubscriptionPlanUseCase,
    DeleteSubscriptionUseCase,
    DeleteUserSubscriptionsUseCase,
    GetSubscriptionUseCase,
    GrantSubscriptionUseCase,
    ListOwnSubscriptionsUseCase,
    ListSubscriptionsUseCase,
    PurchaseSubscriptionUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeHwidStore, FakeUserStore
from tests.modules.settings.factories import SHOP_SETTINGS_FIELDS
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
        UserRepository(subscription_repository.session),
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
                fields_set=SHOP_SETTINGS_FIELDS,
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
        UserRepository(subscription_repository.session),
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


async def test_toggle_does_not_revive_a_row_deleted_mid_call(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9603, "toggle-mid")
    real_disable_user = remnawave_sdk.users.disable_user

    async def disable_then_delete(uuid: object) -> object:
        result = await real_disable_user(uuid)
        async with uow:
            await subscription_repository.mark_deleted(granted.id)
        return result

    monkeypatch.setattr(remnawave_sdk.users, "disable_user", disable_then_delete)
    use_case = _set_enabled(subscription_repository, remnawave_sdk, event_publisher, uow)

    with pytest.raises(ValidationError) as error:
        await use_case(OWNER, SetSubscriptionEnabledDto(subscription_id=granted.id, enabled=False))

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    row = await subscription_repository.get_by_id(granted.id)
    assert row.status is SubscriptionStatus.DELETED


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
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    await use_case(OWNER, granted.id)

    assert remnawave_store[granted.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] == 0
    # the owner is the event's target, so the log finds the edit when filtered by user
    payload = await subscription_repository.session.scalar(
        select(EventOutboxEntry.payload)
        .where(EventOutboxEntry.event_type == "SubscriptionEditedEvent")
        .order_by(EventOutboxEntry.id.desc())
    )
    assert payload is not None and payload["target"]["id"] == granted.user_id


async def test_reset_traffic_brings_a_limited_subscription_back_active(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9703, "limited")
    remnawave_store[granted.remnawave_user_id]["status"] = "LIMITED"
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == granted.id)
        .values(status=SubscriptionStatus.LIMITED)
    )
    use_case = ResetSubscriptionTrafficUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    reset = await use_case(OWNER, granted.id)

    assert reset.status is SubscriptionStatus.ACTIVE
    assert (await subscription_repository.get_by_id(granted.id)).status is SubscriptionStatus.ACTIVE


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
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
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
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
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
    list_devices = AdminListDevicesUseCase(
        subscription_repository, UserRepository(subscription_repository.session), remnawave_sdk, uow
    )
    delete_one = AdminDeleteDeviceUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )
    delete_all = AdminDeleteAllDevicesUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
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


async def _superseded(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    telegram_id: int,
    code: str,
) -> tuple[SubscriptionDto, SubscriptionDto]:
    old = await _granted(grant_use_case, user_repository, plan_repository, telegram_id, code)
    new_plan = await _plan(plan_repository, f"{code}-new")
    live = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=None),
    )
    return old, live


async def test_delete_of_superseded_row_keeps_live_panel_user(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    old, live = await _superseded(
        grant_use_case, change_plan_use_case, user_repository, plan_repository, 9801, "sup-del"
    )
    use_case = DeleteSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(OWNER, old.id)

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert live.remnawave_user_id in remnawave_store
    assert (await subscription_repository.get_by_id(live.id)).status is SubscriptionStatus.ACTIVE


async def test_squads_of_superseded_row_are_rejected(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    old, live = await _superseded(
        grant_use_case, change_plan_use_case, user_repository, plan_repository, 9802, "sup-sq"
    )
    panel_before = dict(remnawave_store[live.remnawave_user_id])
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER,
            UpdateSubscriptionSquadsDto(
                subscription_id=old.id, internal_squads=[uuid4()], external_squad=None
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert remnawave_store[live.remnawave_user_id] == panel_before


async def test_squads_keep_db_unchanged_when_panel_fails(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9803, "sq-fail")

    async def failing_update_user(request: object) -> object:
        raise RemnawavePanelUnavailableError("panel down")

    monkeypatch.setattr(remnawave_sdk.users, "update_user", failing_update_user)
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    with pytest.raises(RemnawavePanelUnavailableError):
        await use_case(
            OWNER,
            UpdateSubscriptionSquadsDto(
                subscription_id=granted.id, internal_squads=[uuid4()], external_squad=None
            ),
        )

    current = await subscription_repository.get_by_id(granted.id)
    assert current.internal_squads == granted.internal_squads


async def test_change_plan_keeping_expiry_carries_the_paid_credit(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    old = await _granted(grant_use_case, user_repository, plan_repository, 9410, "credit-a")
    # as if the customer had paid for this term
    paid = replace(
        old.plan_snapshot,
        price_paid=Decimal("300"),
        duration_days=30,
        credit_paid=None,
        credit_days=None,
    )
    await subscription_repository.session.execute(
        update(Subscription).where(Subscription.id == old.id).values(plan_snapshot=paid.to_json())
    )
    new_plan = await _plan(plan_repository, "credit-b")

    changed = await change_plan_use_case(
        OWNER,
        ChangeSubscriptionPlanDto(subscription_id=old.id, plan_id=new_plan.id, duration_days=None),
    )

    assert changed.expire_at == old.expire_at
    assert changed.plan_snapshot.effective_credit_paid == Decimal("300")
    assert changed.plan_snapshot.effective_credit_days == 30


async def test_squads_are_restored_in_the_panel_when_deleted_mid_edit(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9804, "sq-del")
    panel_before = dict(remnawave_store[granted.remnawave_user_id])
    real_update_user = remnawave_sdk.users.update_user
    calls = 0

    async def update_then_delete(request: object) -> object:
        nonlocal calls
        calls += 1
        result = await real_update_user(request)
        if calls == 1:
            async with uow:
                await subscription_repository.mark_deleted(granted.id)
        return result

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_then_delete)
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER,
            UpdateSubscriptionSquadsDto(
                subscription_id=granted.id, internal_squads=[uuid4()], external_squad=None
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert calls == 2
    restored = dict(remnawave_store[granted.remnawave_user_id])
    # the fake panel stamps updatedAt on every write
    restored.pop("updatedAt")
    panel_before.pop("updatedAt")
    assert restored == panel_before


async def test_squads_rollback_follows_the_plan_change_that_superseded_the_row(
    grant_use_case: GrantSubscriptionUseCase,
    change_plan_use_case: ChangeSubscriptionPlanUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9805, "sq-succ")
    new_plan = await _plan(plan_repository, "sq-succ-new")
    successor_squad = uuid4()
    real_update_user = remnawave_sdk.users.update_user
    sent: list[UpdateUserRequestDto] = []
    successor_id = 0

    async def update_then_change(request: UpdateUserRequestDto) -> object:
        nonlocal successor_id
        sent.append(request)
        result = await real_update_user(request)
        if len(sent) == 1:
            # a plan change lands while the squads edit is in flight; it keeps the panel user
            successor = await change_plan_use_case(
                OWNER,
                ChangeSubscriptionPlanDto(
                    subscription_id=granted.id, plan_id=new_plan.id, duration_days=None
                ),
            )
            successor_id = successor.id
            async with uow:
                await subscription_repository.update_squads(
                    UpdateSubscriptionSquadsDto(
                        subscription_id=successor.id,
                        internal_squads=[successor_squad],
                        external_squad=None,
                    )
                )
        return result

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_then_change)
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER,
            UpdateSubscriptionSquadsDto(
                subscription_id=granted.id, internal_squads=[uuid4()], external_squad=None
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert successor_id != 0
    # the panel user now belongs to the successor: its squads win, not the deleted row's
    assert sent[-1].active_internal_squads == [successor_squad]


async def test_limits_are_restored_in_the_panel_when_deleted_mid_edit(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = await _granted(grant_use_case, user_repository, plan_repository, 9806, "lim-del")
    devices_before = remnawave_store[granted.remnawave_user_id]["hwidDeviceLimit"]
    real_update_user = remnawave_sdk.users.update_user
    calls = 0

    async def update_then_delete(request: object) -> object:
        nonlocal calls
        calls += 1
        result = await real_update_user(request)
        if calls == 1:
            async with uow:
                await subscription_repository.mark_deleted(granted.id)
        return result

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_then_delete)
    use_case = UpdateSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER,
            UpdateSubscriptionDto(subscription_id=granted.id, device_limit=devices_before + 5),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert calls == 2
    assert remnawave_store[granted.remnawave_user_id]["hwidDeviceLimit"] == devices_before
    row = await subscription_repository.get_by_id(granted.id)
    assert row.device_limit != devices_before + 5


async def test_an_admin_can_neither_see_nor_touch_the_owners_own_subscription(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    owner = await user_repository.create(
        CreateUserDto(name="boss", telegram_id=9100, role=Role.OWNER)
    )
    admin = await user_repository.create(
        CreateUserDto(name="helper", telegram_id=9101, role=Role.ADMIN)
    )
    plan = await _plan(plan_repository, "ownersvpn")
    # the owner gives themselves a subscription: their own account is in reach
    subscription = await grant_use_case(
        owner, GrantSubscriptionDto(user_id=owner.id, plan_id=plan.id, duration_days=30)
    )
    get = GetSubscriptionUseCase(
        subscription_repository, user_repository, PanelTrafficUsage(remnawave_sdk), uow
    )
    listing = ListSubscriptionsUseCase(subscription_repository, user_repository, uow)
    delete = DeleteSubscriptionUseCase(
        subscription_repository,
        user_repository,
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )

    with pytest.raises(NotFoundError) as hidden:
        await get(admin, subscription.id)
    with pytest.raises(NotFoundError):
        await delete(admin, subscription.id)
    items, total = await listing(admin, ListSubscriptionsDto())

    assert hidden.value.code is ErrorCode.SUBSCRIPTION_NOT_FOUND
    assert subscription.id not in [item.subscription.id for item in items]
    assert (await get(owner, subscription.id)).subscription.id == subscription.id
    owner_items, _ = await listing(owner, ListSubscriptionsDto())
    assert subscription.id in [item.subscription.id for item in owner_items]


async def test_grant_to_an_anonymized_account_is_not_found(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    session: AsyncSession,
) -> None:
    gone = await user_repository.create(CreateUserDto(name="gone", telegram_id=9102))
    await session.execute(update(User).where(User.id == gone.id).values(deleted_at=datetime_now()))
    plan = await _plan(plan_repository, "togone")

    with pytest.raises(NotFoundError):
        await grant_use_case(
            OWNER, GrantSubscriptionDto(user_id=gone.id, plan_id=plan.id, duration_days=30)
        )


async def _channel_guarded_trial(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    telegram_id: int,
) -> SubscriptionDto:
    granted = await _granted(
        grant_use_case, user_repository, plan_repository, telegram_id, f"guard{telegram_id}"
    )
    await session.execute(
        update(Subscription).where(Subscription.id == granted.id).values(is_trial=True)
    )
    async with uow:
        await SettingsRepository(session).update_bot_requirements(
            UpdateBotRequirementsDto(
                channel_required=True,
                channel_id=-100,
                channel_url="https://t.me/x",
                trial_channel_guard=True,
            )
        )
    return granted


def _membership_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> ApplyChannelMembershipUseCase:
    session = subscription_repository.session
    return ApplyChannelMembershipUseCase(
        subscription_repository,
        UserRepository(session),
        SettingsRepository(session),
        remnawave_sdk,
        SubscriptionLifecycleService(subscription_repository),
        event_publisher,
        uow,
    )


async def test_channel_leave_pauses_a_trial_and_rejoin_resumes_it(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    trial = await _channel_guarded_trial(
        grant_use_case, user_repository, plan_repository, session, uow, 9701
    )
    use_case = _membership_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)
    leave = ChannelMembershipDto(telegram_id=9701, chat_id=-100, joined=False)

    assert await use_case.system(leave) is not None
    paused = await subscription_repository.get_by_id(trial.id)
    assert paused.status is SubscriptionStatus.DISABLED and paused.paused_by_channel_leave
    assert remnawave_store[trial.remnawave_user_id]["status"] == "DISABLED"

    assert await use_case.system(replace(leave, joined=True)) is not None
    resumed = await subscription_repository.get_by_id(trial.id)
    assert resumed.status is SubscriptionStatus.ACTIVE and not resumed.paused_by_channel_leave


async def test_channel_rejoin_keeps_an_admin_disabled_trial_disabled(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    trial = await _channel_guarded_trial(
        grant_use_case, user_repository, plan_repository, session, uow, 9702
    )
    await _set_enabled(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, SetSubscriptionEnabledDto(subscription_id=trial.id, enabled=False)
    )
    use_case = _membership_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)

    joined = ChannelMembershipDto(telegram_id=9702, chat_id=-100, joined=True)
    assert await use_case.system(joined) is None
    assert (await subscription_repository.get_by_id(trial.id)).status is (
        SubscriptionStatus.DISABLED
    )


async def test_own_subscriptions_keep_an_expired_one_for_renewal(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    expired = await _granted(grant_use_case, user_repository, plan_repository, 9703, "own1")
    deleted = await _granted(grant_use_case, user_repository, plan_repository, 9704, "own2")
    for subscription_id, status in (
        (expired.id, SubscriptionStatus.EXPIRED),
        (deleted.id, SubscriptionStatus.DELETED),
    ):
        await session.execute(
            update(Subscription).where(Subscription.id == subscription_id).values(status=status)
        )
    use_case = ListOwnSubscriptionsUseCase(subscription_repository, uow)

    owner = await user_repository.find_by_id(expired.user_id)
    other = await user_repository.find_by_id(deleted.user_id)
    assert owner is not None and other is not None
    assert [s.id for s in await use_case(owner)] == [expired.id]
    assert await use_case(other) == []


def _delete_all(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> DeleteUserSubscriptionsUseCase:
    return DeleteUserSubscriptionsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )


async def test_deleting_all_of_a_users_subscriptions_removes_their_panel_users(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="many", telegram_id=9901))
    other = await user_repository.create(CreateUserDto(name="other", telegram_id=9902))
    plan = await _plan(plan_repository, "delete-all")
    mine = [
        await grant_use_case(
            OWNER, GrantSubscriptionDto(user_id=buyer.id, plan_id=plan.id, duration_days=30)
        )
        for _ in range(2)
    ]
    theirs = await grant_use_case(
        OWNER, GrantSubscriptionDto(user_id=other.id, plan_id=plan.id, duration_days=30)
    )

    result = await _delete_all(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, buyer.id
    )

    assert result.deleted == 2
    for subscription in mine:
        row = await subscription_repository.get_by_id(subscription.id)
        assert row.status is SubscriptionStatus.DELETED
        assert subscription.remnawave_user_id not in remnawave_store
    assert theirs.remnawave_user_id in remnawave_store
    # nothing live left: a repeat deletes nothing
    again = await _delete_all(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, buyer.id
    )
    assert again.deleted == 0


async def test_an_admin_cannot_delete_the_owners_subscriptions(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    owner = await user_repository.create(
        CreateUserDto(name="boss", telegram_id=9903, role=Role.OWNER)
    )
    admin = await user_repository.create(
        CreateUserDto(name="helper", telegram_id=9904, role=Role.ADMIN)
    )

    with pytest.raises(NotFoundError):
        await _delete_all(subscription_repository, remnawave_sdk, event_publisher, uow)(
            admin, owner.id
        )


async def test_an_admin_changes_their_own_subscription_only_with_staff_self_manage(
    grant_use_case: GrantSubscriptionUseCase,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(name="self", telegram_id=9150, role=Role.ADMIN)
        )
        plan = await _plan(plan_repository, "selfvpn")
        # a refused call rolls back, the account must outlive it
        await uow.commit()
    grant = GrantSubscriptionDto(user_id=admin.id, plan_id=plan.id, duration_days=30)
    update = UpdateSubscriptionUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        event_publisher,
        uow,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(PermissionDeniedError):
        await grant_use_case(admin, grant)

    allowed = admin.model_copy(update={"permission_grants": [Permission.STAFF_SELF_MANAGE.value]})
    subscription = await grant_use_case(allowed, grant)
    change = UpdateSubscriptionDto(subscription_id=subscription.id, device_limit=7)
    with pytest.raises(PermissionDeniedError):
        await update(admin, change)
    updated = await update(allowed, change)

    assert updated.device_limit == 7
