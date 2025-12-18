from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode, SubManager
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.bot.states import MainMenu
from src.core.constants import USER_KEY
from src.core.enums import MediaType
from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PlanSnapshotDto, UserDto
from src.infrastructure.taskiq.tasks.subscriptions import trial_subscription_task
from src.services.notification import NotificationService
from src.services.plan import PlanService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService

router = Router(name=__name__)


async def on_start_dialog(
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Started dialog")
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@inject
@router.message(CommandStart(ignore_case=True))
async def on_start_command(
    message: Message,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_RULES_ACCEPT)
async def on_rules_accept(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Accepted rules")
    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_CHANNEL_CONFIRM)
async def on_channel_confirm(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Cofirmed join channel")
    await on_start_dialog(user, dialog_manager)


@inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan = await plan_service.get_trial_plan()

    if not plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-trial-unavailable"),
        )
        raise ValueError("Trial plan not exist")

    trial = PlanSnapshotDto.from_plan(plan, plan.durations[0].days)
    await trial_subscription_task.kiq(user, trial)


@inject
async def on_device_delete(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    await sub_manager.load_data()
    selected_device = sub_manager.item_id
    user: UserDto = sub_manager.middleware_data[USER_KEY]

    if user.current_subscription and user.current_subscription.device_limit:
        await remnawave_service.delete_device(user=user, hwid=selected_device)
        logger.info(f"{log(user)} Deleted self device '{selected_device}'")

    await sub_manager.switch_to(state=MainMenu.MAIN)


@inject
async def show_reason(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription = user.current_subscription

    if subscription:
        kwargs = {
            "status": subscription.get_status,
            "is_trial": subscription.is_trial,
            "traffic_strategy": subscription.traffic_limit_strategy,
            "reset_time": subscription.get_expire_time,
        }
    else:
        kwargs = {"status": False}

    await callback.answer(
        text=i18n.get("ntf-connect-not-available", **get_translated_kwargs(i18n, kwargs)),
        show_alert=True,
    )


@inject
async def on_show_qr(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    ref_link = await referral_service.get_ref_link(user.referral_code)
    ref_qr = referral_service.get_ref_qr(ref_link)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="",
            media=ref_qr,
            media_type=MediaType.PHOTO,
        ),
    )


@inject
async def on_withdraw_points(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(
        text=i18n.get("ntf-invite-withdraw-points-error"),
        show_alert=True,
    )


@inject
async def on_invite(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    if await settings_service.is_referral_enable():
        await dialog_manager.switch_to(state=MainMenu.INVITE)
    else:
        return
