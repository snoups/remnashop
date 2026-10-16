from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.constants import USER_KEY
from app.core.enums import PromocodeRewardType
from app.modules.subscriptions import ListOwnActiveSubscriptionsUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import label_with_icon, render_window_text
from app.telegram.i18n import format_datetime, get_translator


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
        "cancel_text": label_with_icon(runner, "btn-promocode.cancel"),
    }


@inject
async def promocode_target_getter(
    dialog_manager: DialogManager,
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    active = await list_own_active_subscriptions(user)
    subscriptions = [
        {
            "id": sub.id,
            "label": f"{sub.plan_snapshot.name} — {format_datetime(sub.expire_at)}",
        }
        for sub in active
    ]
    return {
        "subscriptions": subscriptions,
        "target_message": render_window_text(runner, "msg-promocode-target"),
        "cancel_text": label_with_icon(runner, "btn-promocode.cancel"),
    }


@inject
async def promocode_confirm_getter(
    dialog_manager: DialogManager,
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    reward_type = dialog_manager.dialog_data.get("promo_reward_type", "")

    will_replace = False
    if reward_type == PromocodeRewardType.SUBSCRIPTION.value:
        will_replace = len(await list_own_active_subscriptions(user)) > 0

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
        "confirm_text": label_with_icon(runner, "btn-promocode.confirm"),
        "cancel_text": label_with_icon(runner, "btn-promocode.cancel"),
    }
