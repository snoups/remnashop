from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.filters import SuperDevFilter
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto

router = Router(name=__name__)


@inject
@router.message(Command("test"), SuperDevFilter())
async def on_test_command(
    message: Message,
    user: UserDto,
) -> None:
    logger.info(f"{log(user)} Test command executed")

    logger.critical(user.current_subscription)
    # logger.critical(user.transactions)
    # logger.critical(user.subscriptions)
    # logger.critical(user.promocode_activations)
    raise UnknownState("test_state")
    # raise UnknownIntent("test_intent")


@inject
async def show_dev_popup(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(text=i18n.get("development"), show_alert=True)
