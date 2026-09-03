from typing import Any, Final, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.core.enums import BannerName, SubscriptionStatus
from app.modules.banners import BannerRepository
from app.modules.subscriptions import (
    GetAvailableTrialUseCase,
    ListDevicesUseCase,
    SubscriptionRepository,
)
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.i18n import get_translator

_KNOWN_PLATFORMS: Final[frozenset[str]] = frozenset({"ios", "android", "windows", "macos", "linux"})


def _platform_icon_key(platform: Optional[str]) -> str:
    normalized = (platform or "default").lower()
    return normalized if normalized in _KNOWN_PLATFORMS else "default"


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    banner_repository: FromDishka[BannerRepository],
    subscription_repository: FromDishka[SubscriptionRepository],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    banner = await get_banner_media(
        banner_repository, config, BannerName.MENU, user.language, config.default_locale
    )

    active = await subscription_repository.get_active_by_user(user.id)
    subscription = active[0] if active else None

    trial_result = await get_available_trial(user)
    trial_available = trial_result.is_trial_available and trial_result.plan is not None
    connectable = subscription is not None and subscription.status == SubscriptionStatus.ACTIVE

    data: dict[str, Any] = {
        "banner": banner,
        "menu_text": runner.get("msg-main-menu", name=user.name),
        "connect_text": runner.get("btn-menu.connect"),
        "connect_url": subscription.url if subscription is not None else "",
        "trial_text": runner.get("btn-menu.trial"),
        "devices_text": runner.get("btn-menu.devices"),
        "subscription_text": runner.get("btn-menu.subscription"),
        "has_subscription": subscription is not None,
        "connectable": connectable,
        "trial_available": trial_available,
        "has_device_limit": subscription is not None and subscription.effective_device_limit != 0,
    }
    return data


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    subscription_repository: FromDishka[SubscriptionRepository],
    list_devices: FromDishka[ListDevicesUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)

    devices = await list_devices(user)
    subscription = await subscription_repository.get_single_active_subscription_or_raise(user.id)

    formatted: list[dict[str, Any]] = [
        {
            "index": index,
            "hwid": device.hwid,
            "label": runner.get(
                "btn-devices.item",
                platform_icon=runner.get(f"platform-icon.{_platform_icon_key(device.platform)}"),
                platform=device.platform or "?",
                device_model=device.device_model or "?",
                created_at=device.created_at.strftime("%d.%m.%Y"),
            ),
        }
        for index, device in enumerate(devices)
    ]
    dialog_manager.dialog_data["hwid_map"] = formatted

    return {
        "devices": formatted,
        "has_devices": len(formatted) > 0,
        "devices_header": runner.get(
            "msg-menu-devices",
            current_count=len(formatted),
            max_count=subscription.effective_device_limit,
        ),
        "empty_text": runner.get("btn-devices.empty"),
        "delete_all_text": runner.get("btn-devices.delete-all"),
        "reissue_text": runner.get("btn-devices.reissue"),
        "back_text": runner.get("btn-back.general"),
    }


@inject
async def device_confirm_delete_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    return {
        "confirm_message": runner.get("msg-menu-devices-confirm-delete"),
        "confirm_delete_text": runner.get("btn-devices.confirm-delete"),
        "back_text": runner.get("btn-back.general"),
    }


@inject
async def device_confirm_delete_all_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    return {
        "confirm_message": runner.get("msg-menu-devices-confirm-delete-all"),
        "confirm_delete_text": runner.get("btn-devices.confirm-delete"),
        "back_text": runner.get("btn-back.general"),
    }


@inject
async def device_confirm_reissue_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    return {
        "confirm_message": runner.get("msg-menu-devices-confirm-reissue"),
        "confirm_reissue_text": runner.get("btn-devices.confirm-reissue"),
        "cancel_text": runner.get("btn-devices.cancel-reissue"),
    }
