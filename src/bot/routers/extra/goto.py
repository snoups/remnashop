from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode, StartMode
from loguru import logger

from src.bot.states import DashboardUser, Subscription, state_from_string
from src.core.constants import GOTO_PREFIX, PURCHASE_PREFIX
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto

router = Router(name=__name__)


@router.callback_query(F.data.startswith(GOTO_PREFIX))
async def on_goto(callback: CallbackQuery, dialog_manager: DialogManager, user: UserDto) -> None:
    logger.info(f"{log(user)} Go to '{callback.data}'")
    data = callback.data.removeprefix(GOTO_PREFIX)  # type: ignore[union-attr]

    if data.startswith(PURCHASE_PREFIX):
        # TODO: Implement a transition to a specific type of purchase
        # There shit with data...
        await dialog_manager.bg(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
        ).start(
            state=Subscription.MAIN,
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
        return

    state = state_from_string(data)

    if not state:
        logger.warning(f"{log(user)} Trying go to not exist state '{data}'")
        return

    if state == DashboardUser.MAIN:
        parts = data.split(":")

        try:
            target_telegram_id = int(parts[2])
        except ValueError:
            logger.warning(f"{log(user)} Invalid target_telegram_id in callback: {parts[2]}")

        await dialog_manager.bg(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
        ).start(
            state=DashboardUser.MAIN,
            data={"target_telegram_id": target_telegram_id},
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.EDIT,
        )
        logger.debug(f"{log(user)} Redirected to user '{target_telegram_id}'")
        return

    logger.debug(f"{log(user)} Redirected to '{state}'")
    await dialog_manager.bg(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    ).start(
        state=state,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
