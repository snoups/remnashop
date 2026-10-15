from typing import Any, Final, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.subscriptions import (
    GetAvailableTrialUseCase,
    ListDevicesUseCase,
    ListOwnActiveSubscriptionsUseCase,
)
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data
from app.telegram.dialogs.rendering import (
    label_with_icon,
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import format_date, get_translator

_KNOWN_PLATFORMS: Final[frozenset[str]] = frozenset({"ios", "android", "windows", "macos", "linux"})


def _platform_icon_key(platform: Optional[str]) -> str:
    normalized = (platform or "default").lower()
    return normalized if normalized in _KNOWN_PLATFORMS else "default"


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    window = await dialog_config_cache.get_window("menu.main")
    # No banner name means the admin turned the banner off for this window --
    # not "fall back to something".
    banner = (
        await get_banner_media(get_banner, config, user, window.banner_name)
        if window.banner_name
        else None
    )

    data: dict[str, Any] = await build_condition_data(
        user, list_own_active_subscriptions, get_available_trial
    )
    data["banner"] = banner
    data["menu_text"] = render_window_text(runner, "msg-main-menu", **resolve_variable_kwargs(data))
    data["subscription_text"] = label_with_icon(runner, "btn-menu.subscription")
    data["buttons"] = await render_dialog_buttons("menu.main", dialog_config_cache, runner, data)
    return data


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    list_devices: FromDishka[ListDevicesUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)

    devices = await list_devices(user)
    subscription = (await list_own_active_subscriptions(user))[0]

    formatted: list[dict[str, Any]] = [
        {
            "index": index,
            "hwid": device.hwid,
            "label": runner.get(
                "btn-devices.item",
                platform_icon=runner.get(f"platform-icon.{_platform_icon_key(device.platform)}"),
                platform=device.platform or "?",
                device_model=device.device_model or "?",
                created_at=format_date(device.created_at),
            ),
        }
        for index, device in enumerate(devices)
    ]
    dialog_manager.dialog_data["hwid_map"] = formatted

    data: dict[str, Any] = {
        "devices": formatted,
        "has_devices": len(formatted) > 0,
        "devices_header": render_window_text(
            runner,
            "msg-menu-devices",
            devices_current=len(formatted),
            devices_max=subscription.effective_device_limit,
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
        "confirm_message": render_window_text(
            runner, "msg-menu-devices-confirm-delete", **resolve_variable_kwargs({})
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
        "confirm_message": render_window_text(
            runner, "msg-menu-devices-confirm-delete-all", **resolve_variable_kwargs({})
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
        "confirm_message": render_window_text(
            runner, "msg-menu-devices-confirm-reissue", **resolve_variable_kwargs({})
        )
    }
    data["buttons"] = await render_dialog_buttons(
        "menu.device_confirm_reissue", dialog_config_cache, runner, data
    )
    return data
