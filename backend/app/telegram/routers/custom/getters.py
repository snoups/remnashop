from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.subscriptions import GetAvailableTrialUseCase, ListOwnActiveSubscriptionsUseCase
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data
from app.telegram.dialogs.rendering import (
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.dialogs.state_pool import resolve_custom_window_key
from app.telegram.i18n import get_translator


@inject
async def custom_window_getter(
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
    key = await resolve_custom_window_key(
        dialog_manager.current_context().state, dialog_config_cache
    )
    if key is None:
        # The window behind this slot was deleted while the user sat in it.
        return {
            "banner": None,
            "window_text": render_window_text(runner, "msg-window-gone"),
            "buttons": [],
        }

    window = await dialog_config_cache.get_window(key)
    banner = (
        await get_banner_media(get_banner, config, user, window.banner_name)
        if window.banner_name is not None
        else None
    )

    data: dict[str, Any] = await build_condition_data(
        user, list_own_active_subscriptions, get_available_trial
    )
    data["banner"] = banner
    data["window_text"] = render_window_text(
        runner, f"msg-dialog-{key}", **resolve_variable_kwargs(data)
    )
    data["buttons"] = await render_dialog_buttons(key, dialog_config_cache, runner, data)
    return data
