from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.referrals import GetReferralSettingsUseCase
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import GetAvailableTrialUseCase, ListOwnActiveSubscriptionsUseCase
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data, menu_flags
from app.telegram.dialogs.rendering import (
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import get_translator


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    window = await dialog_config_cache.get_window("menu.main")
    # no banner name: the admin turned the banner off for this window, no fallback
    banner = (
        await get_banner_media(get_banner, config, user, window.banner_name)
        if window.banner_name
        else None
    )

    active = await list_own_active_subscriptions(user)
    can_purchase, referral_enabled = await menu_flags(
        active, get_shop_settings, get_referral_settings
    )
    data: dict[str, Any] = await build_condition_data(
        user,
        active,
        get_available_trial,
        can_purchase=can_purchase,
        referral_enabled=referral_enabled,
    )
    data["banner"] = banner
    data["menu_text"] = render_window_text(runner, "msg-main-menu", **resolve_variable_kwargs(data))
    data["buttons"] = await render_dialog_buttons("menu.main", dialog_config_cache, runner, data)
    return data
