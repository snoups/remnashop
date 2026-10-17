from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from loguru import logger

from app.core.constants import USER_KEY
from app.core.enums import PurchaseType
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.subscriptions import (
    ActivateTrialSubscriptionDto,
    ActivateTrialSubscriptionUseCase,
    GetAvailableTrialUseCase,
)
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.routers.purchase.handlers import PLAN_CODE_KEY
from app.telegram.states import MainMenu, Purchase

router = Router(name=__name__)


@router.message(CommandStart())
async def on_start_command(message: Message, user: UserDto, dialog_manager: DialogManager) -> None:
    logger.info(f"{user.log} Started menu dialog")
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("paysupport"))
async def on_paysupport_command(
    message: Message, user: UserDto, i18n: FromDishka[TranslatorHub]
) -> None:
    logger.info(f"{user.log} Called '/paysupport' command")
    await message.answer(get_translator(i18n, user).get("msg-paysupport"))


@inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    activate_trial_subscription: FromDishka[ActivateTrialSubscriptionUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    result = await get_available_trial(user)

    if result.plan is None or not result.is_trial_available:
        await callback.answer(runner.get("ntf-common.trial-unavailable"), show_alert=True)
        return

    if not result.is_free:
        # a paid trial is bought like any plan, opened the way a plan link opens it
        await dialog_manager.start(
            Purchase.PLAN,
            data={"purchase_type": PurchaseType.NEW.value, PLAN_CODE_KEY: result.plan.public_code},
        )
        return

    try:
        await activate_trial_subscription(user, ActivateTrialSubscriptionDto(plan=result.plan))
    except (NotFoundError, ValidationError):
        logger.exception(f"{user.log} Trial activation failed")
        await callback.answer(runner.get("ntf-common.trial-unavailable"), show_alert=True)
        return

    await dialog_manager.switch_to(state=MainMenu.MAIN)
