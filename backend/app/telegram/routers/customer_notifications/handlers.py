from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from fluentogram import TranslatorHub

from app.core.constants import (
    CUSTOMER_NOTIFICATION_BUY_CALLBACK,
    CUSTOMER_NOTIFICATION_CLOSE_CALLBACK,
    CUSTOMER_NOTIFICATION_RENEW_PREFIX,
    CUSTOMER_NOTIFICATION_REVOKE_SESSIONS_CALLBACK,
)
from app.core.enums import PurchaseType
from app.modules.auth import RevokeOtherCabinetSessionsUseCase
from app.modules.subscriptions import ListOwnSubscriptionsUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu, Purchase

router = Router(name=__name__)


@router.callback_query(F.data == CUSTOMER_NOTIFICATION_CLOSE_CALLBACK)
async def on_notification_close(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        # a double tap finds the message already gone
        with suppress(TelegramAPIError):
            await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data.startswith(CUSTOMER_NOTIFICATION_RENEW_PREFIX))
async def on_notification_renew(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
) -> None:
    raw = (callback.data or "").removeprefix(CUSTOMER_NOTIFICATION_RENEW_PREFIX)
    active = await list_own_subscriptions(user)
    # a trial or an expired subscription can't be renewed in the bot: a new purchase can
    target = next((s for s in active if str(s.id) == raw and not s.is_trial), None)
    data: dict[str, Any] = (
        {"purchase_type": PurchaseType.NEW.value}
        if target is None
        else {"purchase_type": PurchaseType.RENEW.value, SELECTED_SUBSCRIPTION_KEY: target.id}
    )
    await callback.answer()
    await _open_purchase(dialog_manager, data)


@router.callback_query(F.data == CUSTOMER_NOTIFICATION_BUY_CALLBACK)
async def on_notification_buy(callback: CallbackQuery, dialog_manager: DialogManager) -> None:
    await callback.answer()
    await _open_purchase(dialog_manager, {"purchase_type": PurchaseType.NEW.value})


@router.callback_query(F.data == CUSTOMER_NOTIFICATION_REVOKE_SESSIONS_CALLBACK)
async def on_notification_revoke_sessions(
    callback: CallbackQuery,
    user: UserDto,
    i18n: FromDishka[TranslatorHub],
    revoke_sessions: FromDishka[RevokeOtherCabinetSessionsUseCase],
) -> None:
    # every cabinet session, the unrecognized one included
    await revoke_sessions(user, None)
    runner = get_translator(i18n, user)
    await callback.answer(runner.get("ntf-customer-sessions-revoked"), show_alert=True)


async def _open_purchase(dialog_manager: DialogManager, data: dict[str, Any]) -> None:
    # under the menu, so a purchase that can't start or is left returns there
    await dialog_manager.start(
        MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.NO_UPDATE
    )
    await dialog_manager.start(Purchase.PLAN, data=data, show_mode=ShowMode.SEND)
