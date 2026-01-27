from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode, StartMode
from loguru import logger

from src.application.dto import UserDto
from src.core.constants import GOTO_PREFIX, PAYMENT_PREFIX, TARGET_TELEGRAM_ID
from src.telegram.states import DashboardUser, Subscription, state_from_string

router = Router(name=__name__)


@router.callback_query(F.data.startswith(GOTO_PREFIX))
async def on_goto(callback: CallbackQuery, dialog_manager: DialogManager, user: UserDto) -> None:
    logger.info(f"{user.log} Go to '{callback.data}'")
    data = callback.data.removeprefix(GOTO_PREFIX)  # type: ignore[union-attr]

    if data.startswith(PAYMENT_PREFIX):
        # TODO: Implement a transition to a specific type of payment
        # There shit with data...
        await dialog_manager.bg(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
        ).start(
            state=Subscription.MAIN,
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
        await callback.answer()
        return

    state = state_from_string(data)

    if not state:
        logger.warning(f"{user.log} Trying go to not exist state '{data}'")
        await callback.answer()
        return

    if state == DashboardUser.MAIN:
        parts = data.split(":")

        try:
            target_telegram_id = int(parts[2])
        except ValueError:
            logger.warning(f"{user.log} Invalid target_telegram_id in callback: {parts[2]}")

        await dialog_manager.bg(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
        ).start(
            state=DashboardUser.MAIN,
            data={TARGET_TELEGRAM_ID: target_telegram_id},
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
        logger.debug(f"{user.log} Redirected to user '{target_telegram_id}'")
        await callback.answer()
        return

    logger.debug(f"{user.log} Redirected to '{state}'")
    await dialog_manager.bg(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    ).start(
        state=state,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
    await callback.answer()
