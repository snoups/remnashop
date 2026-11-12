from datetime import datetime, timedelta, timezone

import pytest
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy

from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.exceptions import CooldownError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    DeleteDeviceDto,
    SubscriptionRefDto,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    ListDevicesUseCase,
    ReissueSubscriptionUseCase,
)
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.settings.factories import SHOP_SETTINGS_FIELDS
from tests.modules.subscriptions.factories import make_plan_snapshot


async def _create_active_subscription(
    subscription_repository: SubscriptionRepository, user_id: int, remnawave_user_id: int
):
    return await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
            is_trial=False,
            internal_squads=[],
            external_squad=None,
            expire_at=datetime_now() + timedelta(days=30),
            url="https://fake-panel.test/sub/device-test",
            plan_snapshot=make_plan_snapshot(is_trial=False),
        )
    )


def _device(hwid: str, user_id: int, **overrides: object) -> dict:
    return {
        "hwid": hwid,
        "userId": user_id,
        "platform": None,
        "osVersion": None,
        "deviceModel": None,
        "userAgent": None,
        "requestIp": None,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        **overrides,
    }


async def test_lists_the_actors_devices(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-lister"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7001)
    remnawave_hwid_store[7001] = [_device("abc", 7001, platform="android", deviceModel="Pixel")]
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    devices = await use_case(actor, SubscriptionRefDto(subscription_id=subscription.id))

    assert len(devices) == 1
    assert devices[0].hwid == "abc"
    assert devices[0].platform == "android"


async def test_refuses_a_deleted_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="deleted-sub"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7100)
    await subscription_repository.mark_deleted(subscription.id)
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    with pytest.raises(ValidationError):
        await use_case(actor, SubscriptionRefDto(subscription_id=subscription.id))


async def test_device_usecases_refuse_another_users_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="owner"))
    stranger = await user_repository.create(CreateUserDto(name="stranger"))
    subscription = await _create_active_subscription(subscription_repository, owner.id, 7101)
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    with pytest.raises(ValidationError):
        await use_case(stranger, SubscriptionRefDto(subscription_id=subscription.id))


async def test_lists_devices_of_the_chosen_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="two-subs"))
    await _create_active_subscription(subscription_repository, actor.id, 7102)
    second = await _create_active_subscription(subscription_repository, actor.id, 7103)
    remnawave_hwid_store[7102] = []
    remnawave_hwid_store[7103] = [_device("second-hwid", 7103)]
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    devices = await use_case(actor, SubscriptionRefDto(subscription_id=second.id))

    assert [device.hwid for device in devices] == ["second-hwid"]


async def test_deletes_a_device(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7002)
    remnawave_hwid_store[7002] = [_device("delete-me", 7002)]
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)

    await use_case(actor, DeleteDeviceDto(subscription_id=subscription.id, hwid="delete-me"))

    assert remnawave_hwid_store[7002] == []
    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.device_single_reset_at is not None


async def test_rejects_when_disabled(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-disabled"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7003)
    current = await settings_repository.get_shop_settings()
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=current.max_active_subscriptions,
            device_single_reset_enabled=False,
            device_single_reset_cooldown_hours=current.device_single_reset_cooldown_hours,
            device_all_reset_enabled=current.device_all_reset_enabled,
            device_all_reset_cooldown_hours=current.device_all_reset_cooldown_hours,
            link_reset_enabled=current.link_reset_enabled,
            link_reset_cooldown_hours=current.link_reset_cooldown_hours,
            fields_set=SHOP_SETTINGS_FIELDS,
        )
    )
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)

    with pytest.raises(ValidationError):
        await use_case(actor, DeleteDeviceDto(subscription_id=subscription.id, hwid="whatever"))


async def test_rejects_within_cooldown(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-cooldown"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7004)
    current = await settings_repository.get_shop_settings()
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=current.max_active_subscriptions,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=24,
            device_all_reset_enabled=current.device_all_reset_enabled,
            device_all_reset_cooldown_hours=current.device_all_reset_cooldown_hours,
            link_reset_enabled=current.link_reset_enabled,
            link_reset_cooldown_hours=current.link_reset_cooldown_hours,
            fields_set=SHOP_SETTINGS_FIELDS,
        )
    )
    remnawave_hwid_store[7004] = []
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)
    await use_case(actor, DeleteDeviceDto(subscription_id=subscription.id, hwid="first"))

    with pytest.raises(CooldownError):
        await use_case(actor, DeleteDeviceDto(subscription_id=subscription.id, hwid="second"))


async def test_deleting_all_devices_reissues_the_link(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-all"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7005)
    remnawave_store[7005] = _user_payload(
        user_id=7005, username="delete-all-test", expire_at=datetime_now()
    )
    remnawave_hwid_store[7005] = [
        _device("a", 7005),
        _device("b", 7005),
    ]
    use_case = DeleteAllDevicesUseCase(
        subscription_repository, remnawave_sdk, settings_repository, uow
    )

    await use_case(actor, SubscriptionRefDto(subscription_id=subscription.id))

    assert remnawave_hwid_store[7005] == []
    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.url != subscription.url
    assert reloaded.device_all_reset_at is not None


async def test_reissues_the_subscription_link(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="reissuer"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7006)
    remnawave_store[7006] = _user_payload(
        user_id=7006, username="reissue-test", expire_at=datetime_now()
    )
    remnawave_hwid_store[7006] = [_device("a", 7006)]
    use_case = ReissueSubscriptionUseCase(
        subscription_repository, remnawave_sdk, settings_repository, uow
    )

    await use_case(actor, SubscriptionRefDto(subscription_id=subscription.id))

    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.url != subscription.url
    assert reloaded.link_reset_at is not None
    assert remnawave_hwid_store[7006] == []


async def test_a_failed_panel_call_hands_the_cooldown_back(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-refund"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7007)
    current = await settings_repository.get_shop_settings()
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=current.max_active_subscriptions,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=24,
            device_all_reset_enabled=current.device_all_reset_enabled,
            device_all_reset_cooldown_hours=current.device_all_reset_cooldown_hours,
            link_reset_enabled=current.link_reset_enabled,
            link_reset_cooldown_hours=current.link_reset_cooldown_hours,
            fields_set=SHOP_SETTINGS_FIELDS,
        )
    )

    async def panel_down(_: object) -> None:
        raise RuntimeError("panel down")

    monkeypatch.setattr(remnawave_sdk.hwid, "delete_hwid_to_user", panel_down)
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)

    with pytest.raises(RuntimeError):
        await use_case(actor, DeleteDeviceDto(subscription_id=subscription.id, hwid="first"))

    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.device_single_reset_at is None
