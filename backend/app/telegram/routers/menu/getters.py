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
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.rendering import render_dialog_buttons, resolve_variable_kwargs
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
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    window = await dialog_config_cache.get_window("menu.main")
    banner = await get_banner_media(
        banner_repository,
        config,
        window.banner_name or BannerName.MENU,
        user.language,
        config.default_locale,
    )

    active = await subscription_repository.get_active_by_user(user.id)
    subscription = active[0] if active else None

    trial_result = await get_available_trial(user)
    trial_available = trial_result.is_trial_available and trial_result.plan is not None
    connectable = subscription is not None and subscription.status == SubscriptionStatus.ACTIVE

    data: dict[str, Any] = {
        "banner": banner,
        "menu_text": runner.get("msg-main-menu", **resolve_variable_kwargs({"name": user.name})),
        "subscription_text": runner.get("btn-menu.subscription"),
        "has_subscription": subscription is not None,
        "connectable": connectable,
        "trial_available": trial_available,
        "has_device_limit": subscription is not None and subscription.effective_device_limit != 0,
        "connect_url": subscription.url if subscription is not None else "",
    }
    data["buttons"] = await render_dialog_buttons("menu.main", dialog_config_cache, runner, data)
    return data


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    subscription_repository: FromDishka[SubscriptionRepository],
    list_devices: FromDishka[ListDevicesUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
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

    data: dict[str, Any] = {
        "devices": formatted,
        "has_devices": len(formatted) > 0,
        "devices_header": runner.get(
            "msg-menu-devices",
            current_count=len(formatted),
            max_count=subscription.effective_device_limit,
            **resolve_variable_kwargs({}),
        ),
        "empty_text": runner.get("btn-devices.empty"),
    }
    data["buttons"] = await render_dialog_buttons("menu.devices", dialog_config_cache, runner, data)
    return data


@inject
async def device_confirm_delete_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data: dict[str, Any] = {
        "confirm_message": runner.get(
            "msg-menu-devices-confirm-delete", **resolve_variable_kwargs({})
        )
    }
    data["buttons"] = await render_dialog_buttons(
        "menu.device_confirm_delete", dialog_config_cache, runner, data
    )
    return data


@inject
async def device_confirm_delete_all_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data: dict[str, Any] = {
        "confirm_message": runner.get(
            "msg-menu-devices-confirm-delete-all", **resolve_variable_kwargs({})
        )
    }
    data["buttons"] = await render_dialog_buttons(
        "menu.device_confirm_delete_all", dialog_config_cache, runner, data
    )
    return data


@inject
async def device_confirm_reissue_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data: dict[str, Any] = {
        "confirm_message": runner.get(
            "msg-menu-devices-confirm-reissue", **resolve_variable_kwargs({})
        )
    }
    data["buttons"] = await render_dialog_buttons(
        "menu.device_confirm_reissue", dialog_config_cache, runner, data
    )
    return data
