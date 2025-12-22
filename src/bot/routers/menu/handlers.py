from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka.integrations.aiogram_dialog import inject

from src.bot.states import MainMenu

router = Router(name=__name__)


async def on_start_dialog(dialog_manager: DialogManager) -> None:
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@inject
@router.message(CommandStart(ignore_case=True))
async def on_start_command(message: Message, dialog_manager: DialogManager) -> None:
    await on_start_dialog(dialog_manager)
