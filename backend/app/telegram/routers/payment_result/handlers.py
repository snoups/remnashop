from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from app.core.constants import USER_KEY
from app.modules.transactions import GetOwnTransactionUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.purchase.handlers import RETRY_DURATION_KEY, RETRY_PLAN_KEY
from app.telegram.states import Purchase, Subscriptions


def order_id(manager: DialogManager) -> int:
    assert isinstance(manager.start_data, dict)
    return int(manager.start_data["order_id"])


@inject
async def on_open_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    get_own_transaction: FromDishka[GetOwnTransactionUseCase],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    order = await get_own_transaction(user, order_id(dialog_manager))
    await dialog_manager.start(
        Subscriptions.CARD,
        data={SELECTED_SUBSCRIPTION_KEY: order.fulfilled_subscription_id},
        mode=StartMode.RESET_STACK,
    )


@inject
async def on_retry(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    get_own_transaction: FromDishka[GetOwnTransactionUseCase],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    order = await get_own_transaction(user, order_id(dialog_manager))
    await dialog_manager.start(
        Purchase.PLAN,
        data={
            "purchase_type": order.purchase_type.value,
            SELECTED_SUBSCRIPTION_KEY: order.target_subscription_id,
            RETRY_PLAN_KEY: order.plan_id,
            RETRY_DURATION_KEY: order.duration_days,
        },
        mode=StartMode.RESET_STACK,
    )
