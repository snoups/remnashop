from contextlib import suppress
from typing import Optional

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent, UnknownState
from dishka import FromDishka
from fluentogram import TranslatorHub
from loguru import logger

from app.modules.settings import GetShopSettingsUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import label_with_icon
from app.telegram.i18n import get_translator
from app.telegram.notice import answer_notice
from app.telegram.states import MainMenu

# ErrorMiddleware has logged the exception already. A raise from in here is not
# fed back into these handlers, so neither of them can loop.
router = Router(name=__name__)


@router.errors(ExceptionTypeFilter(UnknownIntent, OutdatedIntent, UnknownState))
async def on_lost_context(
    event: ErrorEvent, dialog_manager: DialogManager, user: Optional[UserDto] = None
) -> None:
    # a button from a dialog whose state expired or was evicted: the stale
    # window gives way to a fresh menu
    callback = event.update.callback_query
    if callback is not None:
        with suppress(TelegramAPIError):
            await callback.answer()
            if isinstance(callback.message, Message):
                await callback.message.delete()
    if user is None or user.is_blocked:
        # raised ahead of the user and blacklist middlewares
        return
    try:
        await dialog_manager.start(
            MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
        )
    except Exception:
        logger.exception("Failed to reopen the main menu after a lost dialog context")


@router.errors(ExceptionTypeFilter(Exception))
async def on_unhandled_error(
    event: ErrorEvent,
    dialog_manager: DialogManager,
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        return
    runner = get_translator(i18n, user)
    support = (await get_shop_settings.system()).support_link
    keyboard = (
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=label_with_icon(runner, "btn-menu.support"), url=support
                    )
                ]
            ]
        )
        if support
        else None
    )
    with suppress(TelegramAPIError):
        await answer_notice(
            event.update.callback_query or event.update.message,
            runner.get("ntf-common.unknown-error"),
            # the support button has to outlive the notice's few seconds
            keep=keyboard is not None,
            reply_markup=keyboard,
        )
    message = event.update.message
    if message is not None and (message.text or "").startswith("/start"):
        # the menu is what just failed
        return
    try:
        await dialog_manager.start(
            MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
        )
    except Exception:
        # a menu that fails the same way stops here: errors raised in here aren't handled again
        logger.exception("Failed to reopen the main menu after an error")
