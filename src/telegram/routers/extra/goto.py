from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.dto import UserDto
from src.application.use_cases.user.queries.plans import GetAvailablePlanByCode
from src.core.constants import GOTO_PREFIX, PAYMENT_PREFIX, TARGET_TELEGRAM_ID
from src.core.enums import Deeplink
from src.telegram.states import DashboardUser, MainMenu, Subscription, state_from_string

router = Router(name=__name__)


@router.callback_query(F.data.startswith(GOTO_PREFIX))
async def on_goto(callback: CallbackQuery, dialog_manager: DialogManager, user: UserDto) -> None:
    logger.info(f"{user.log} Try go to '{callback.data}'")
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


@inject
@router.message(CommandStart(deep_link=True, ignore_case=True), F.text.contains(Deeplink.PLAN))
async def on_goto_plan(
    message: Message,
    command: CommandObject,
    dialog_manager: DialogManager,
    user: UserDto,
    get_available_plan_by_code: FromDishka[GetAvailablePlanByCode],
    notifier: FromDishka[Notifier],
) -> None:
    args = command.args or ""
    public_code = args.removeprefix(Deeplink.PLAN.with_underscore)
    plan = await get_available_plan_by_code(user, public_code)

    # TODO: Handle brootforce of plan codes

    if not plan:
        logger.warning(f"{user.log} Plan with code '{public_code}' not found or not available")
        await notifier.notify_user(user=user, i18n_key="ntf-common.plan-not-found")
        return

    logger.info(f"{user.log} Redirected to plan '{public_code}'")

    await dialog_manager.bg(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    ).start(
        state=Subscription.PLAN,
        data={"plan_id": plan.id},
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(CommandStart(deep_link=True, ignore_case=True), F.text.contains(Deeplink.INVITE))
async def on_goto_invite(
    message: Message,
    command: CommandObject,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    if command.args == Deeplink.INVITE:
        logger.info(f"{user.log} Redirected to invite menu")
        await dialog_manager.start(
            state=MainMenu.INVITE,
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
