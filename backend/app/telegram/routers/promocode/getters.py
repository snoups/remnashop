from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import DEFAULT_BANNER_NAME, USER_KEY
from app.core.enums import PromocodeRewardType
from app.core.utils.i18n_helpers import i18n_format_expire_time
from app.modules.banners import BannerRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import get_translator


@inject
async def subscription_main_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    banner_repository: FromDishka[BannerRepository],
    settings_repository: FromDishka[SettingsRepository],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    banner = await get_banner_media(
        banner_repository,
        settings_repository,
        config,
        DEFAULT_BANNER_NAME,
        user.language,
        config.default_locale,
    )
    return {
        "banner": banner,
        "message": render_window_text(runner, "msg-subscription-main"),
        "promocode_text": runner.get("btn-subscription.promocode"),
        "back_text": runner.get("btn-back.general"),
    }


@inject
async def promocode_input_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    return {
        "input_message": render_window_text(runner, "msg-promocode-input"),
        "cancel_text": runner.get("btn-promocode.cancel"),
    }


@inject
async def promocode_target_getter(
    dialog_manager: DialogManager,
    subscription_repository: FromDishka[SubscriptionRepository],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    active = await subscription_repository.get_active_by_user(user.id)
    subscriptions = [
        {
            "id": sub.id,
            "label": f"{sub.plan_snapshot.name} — {i18n_format_expire_time(sub.expire_at)}",
        }
        for sub in active
    ]
    return {
        "subscriptions": subscriptions,
        "target_message": render_window_text(runner, "msg-promocode-target"),
        "cancel_text": runner.get("btn-promocode.cancel"),
    }


@inject
async def promocode_confirm_getter(
    dialog_manager: DialogManager,
    subscription_repository: FromDishka[SubscriptionRepository],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    reward_type = dialog_manager.dialog_data.get("promo_reward_type", "")

    will_replace = False
    if reward_type == PromocodeRewardType.SUBSCRIPTION.value:
        will_replace = len(await subscription_repository.get_active_by_user(user.id)) > 0

    return {
        "confirm_message": render_window_text(
            runner,
            "msg-promocode-confirm",
            promo_code=dialog_manager.dialog_data.get("promo_code", ""),
            promo_reward_type=reward_type,
            promo_reward=dialog_manager.dialog_data.get("promo_reward") or 0,
        ),
        "will_replace_message": render_window_text(runner, "msg-promocode-confirm-will-replace")
        if will_replace
        else "",
        "confirm_text": runner.get("btn-promocode.confirm"),
        "cancel_text": runner.get("btn-promocode.cancel"),
    }
