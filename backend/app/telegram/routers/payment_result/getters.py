from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.constants import USER_KEY
from app.modules.transactions import GetOwnTransactionUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import label_with_icon, render_window_text
from app.telegram.i18n import get_translator
from app.telegram.routers.payment_result.handlers import order_id


@inject
async def success_getter(
    dialog_manager: DialogManager,
    get_own_transaction: FromDishka[GetOwnTransactionUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    order = await get_own_transaction(user, order_id(dialog_manager))
    return {
        "window_text": render_window_text(
            runner,
            "msg-payment-result-success",
            purchase_type=order.purchase_type.value,
            plan_name=order.plan_snapshot.name,
        ),
        "has_subscription": order.fulfilled_subscription_id is not None,
        "subscription_text": label_with_icon(runner, "btn-payment-result.subscription"),
        "menu_text": label_with_icon(runner, "btn-payment-result.menu"),
    }


@inject
async def failed_getter(
    dialog_manager: DialogManager, i18n: FromDishka[TranslatorHub], **kwargs: Any
) -> dict[str, Any]:
    runner = get_translator(i18n, dialog_manager.middleware_data[USER_KEY])
    return {
        "window_text": render_window_text(runner, "msg-payment-result-failed"),
        "menu_text": label_with_icon(runner, "btn-payment-result.menu"),
    }


@inject
async def canceled_getter(
    dialog_manager: DialogManager, i18n: FromDishka[TranslatorHub], **kwargs: Any
) -> dict[str, Any]:
    runner = get_translator(i18n, dialog_manager.middleware_data[USER_KEY])
    return {
        "window_text": render_window_text(runner, "msg-payment-result-canceled"),
        "retry_text": label_with_icon(runner, "btn-payment-result.retry"),
        "menu_text": label_with_icon(runner, "btn-payment-result.menu"),
    }
