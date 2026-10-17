from contextlib import suppress
from typing import Optional

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent, UnknownState
from dishka import FromDishka
from fluentogram import TranslatorHub
from loguru import logger

from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu

# ErrorMiddleware has logged the exception already. A raise from in here is not
# fed back into these handlers, so neither of them can loop.
router = Router(name=__name__)


async def _reply(event: ErrorEvent, text: str) -> None:
    # an alert on a button press also stops its spinner
    with suppress(TelegramAPIError):
        if event.update.callback_query is not None:
            await event.update.callback_query.answer(text, show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(text)


@router.errors(ExceptionTypeFilter(UnknownIntent, OutdatedIntent, UnknownState))
async def on_lost_context(
    event: ErrorEvent,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    # a button from a dialog whose state expired or was evicted: start over at the menu
    if user is not None:
        await _reply(event, get_translator(i18n, user).get("ntf-common.lost-context"))
    try:
        await dialog_manager.start(
            MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
        )
    except Exception:
        logger.exception("Failed to reopen the main menu after a lost dialog context")


@router.errors(ExceptionTypeFilter(Exception))
async def on_unhandled_error(
    event: ErrorEvent,
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    # text only: reopening a menu here could fail the same way again
    if user is not None:
        await _reply(event, get_translator(i18n, user).get("ntf-common.unknown-error"))
