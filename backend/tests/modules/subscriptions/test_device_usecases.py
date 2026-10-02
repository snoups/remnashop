from datetime import datetime, timedelta, timezone

import pytest
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy

from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.exceptions import CooldownError, NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto, DeleteDeviceDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.delete_all_devices import DeleteAllDevicesUseCase
from app.modules.subscriptions.usecases.delete_device import DeleteDeviceUseCase
from app.modules.subscriptions.usecases.list_devices import ListDevicesUseCase
from app.modules.subscriptions.usecases.reissue_subscription import ReissueSubscriptionUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
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


async def test_lists_the_actors_devices(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-lister"))
    await _create_active_subscription(subscription_repository, actor.id, 7001)
    remnawave_hwid_store[7001] = [
        {
            "hwid": "abc",
            "userId": 7001,
            "platform": "android",
            "osVersion": None,
            "deviceModel": "Pixel",
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    ]
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    devices = await use_case(actor)

    assert len(devices) == 1
    assert devices[0].hwid == "abc"
    assert devices[0].platform == "android"


async def test_raises_when_the_actor_has_no_active_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="no-sub"))
    use_case = ListDevicesUseCase(subscription_repository, remnawave_sdk, uow)

    with pytest.raises(NotFoundError):
        await use_case(actor)


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
    remnawave_hwid_store[7002] = [
        {
            "hwid": "delete-me",
            "userId": 7002,
            "platform": None,
            "osVersion": None,
            "deviceModel": None,
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    ]
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)

    await use_case(actor, DeleteDeviceDto(hwid="delete-me"))

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
    await _create_active_subscription(subscription_repository, actor.id, 7003)
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
        )
    )
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)

    with pytest.raises(ValidationError):
        await use_case(actor, DeleteDeviceDto(hwid="whatever"))


async def test_rejects_within_cooldown(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-cooldown"))
    await _create_active_subscription(subscription_repository, actor.id, 7004)
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
        )
    )
    remnawave_hwid_store[7004] = []
    use_case = DeleteDeviceUseCase(subscription_repository, remnawave_sdk, settings_repository, uow)
    await use_case(actor, DeleteDeviceDto(hwid="first"))

    with pytest.raises(CooldownError):
        await use_case(actor, DeleteDeviceDto(hwid="second"))


async def test_deletes_all_devices(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_hwid_store: dict,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="device-deleter-all"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7005)
    remnawave_hwid_store[7005] = [
        {
            "hwid": "a",
            "userId": 7005,
            "platform": None,
            "osVersion": None,
            "deviceModel": None,
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
        {
            "hwid": "b",
            "userId": 7005,
            "platform": None,
            "osVersion": None,
            "deviceModel": None,
            "userAgent": None,
            "requestIp": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    ]
    use_case = DeleteAllDevicesUseCase(
        subscription_repository, remnawave_sdk, settings_repository, uow
    )

    await use_case(actor)

    assert remnawave_hwid_store[7005] == []
    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.device_all_reset_at is not None


async def test_reissues_the_subscription_link(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="reissuer"))
    subscription = await _create_active_subscription(subscription_repository, actor.id, 7006)
    remnawave_store[7006] = _user_payload(
        user_id=7006, username="reissue-test", expire_at=datetime_now()
    )
    use_case = ReissueSubscriptionUseCase(
        subscription_repository, remnawave_sdk, settings_repository, uow
    )

    await use_case(actor)

    reloaded = await subscription_repository.get_by_id(subscription.id)
    assert reloaded.url != subscription.url
    assert reloaded.link_reset_at is not None
