from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier, Remnawave, TranslatorRunner
from src.application.common.dao import SettingsDao, SubscriptionDao
from src.application.dto import MediaDescriptorDto, MessagePayloadDto, PlanSnapshotDto, UserDto
from src.application.services import BotService
from src.application.use_cases.referral import GenerateReferralQr
from src.application.use_cases.subscription import (
    ActivateTrialSubscription,
    ActivateTrialSubscriptionDto,
)
from src.application.use_cases.user import GetAvailableTrial
from src.core.constants import USER_KEY
from src.core.enums import MediaType
from src.core.utils.i18n_helpers import i18n_format_expire_time
from src.core.utils.time import get_traffic_reset_delta
from src.telegram.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.telegram.states import MainMenu

router = Router(name=__name__)


async def on_start_dialog(user: UserDto, dialog_manager: DialogManager) -> None:
    logger.info(f"{user.log} Started dialog")
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(CommandStart(ignore_case=True))
async def on_start_command(message: Message, user: UserDto, dialog_manager: DialogManager) -> None:
    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_RULES_ACCEPT)
async def on_rules_accept(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_CHANNEL_CONFIRM)
async def on_channel_confirm(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    await on_start_dialog(user, dialog_manager)


@inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    get_available_trial: FromDishka[GetAvailableTrial],
    activate_trial_subscription: FromDishka[ActivateTrialSubscription],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan = await get_available_trial.system(user)

    if not plan:
        await notifier.notify_user(user=user, i18n_key="ntf-common.trial-unavailable")
        raise ValueError("Trial plan not exist")

    trial = PlanSnapshotDto.from_plan(plan, plan.durations[0].days)
    await activate_trial_subscription.system(ActivateTrialSubscriptionDto(user, trial))


@inject
async def on_device_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave: FromDishka[Remnawave],
) -> None:
    selected_short_hwid = dialog_manager.item_id  # type: ignore[attr-defined]
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    hwid_map = dialog_manager.dialog_data.get("hwid_map")

    if not hwid_map:
        raise ValueError(f"Selected '{selected_short_hwid}' HWID, but 'hwid_map' is missing")

    full_hwid = next((d["hwid"] for d in hwid_map if d["short_hwid"] == selected_short_hwid), None)

    if not full_hwid:
        raise ValueError(f"Full HWID not found for '{selected_short_hwid}'")

    current_subscription = await subscription_dao.get_current(user.telegram_id)

    if not (current_subscription and current_subscription.device_limit):
        raise ValueError("User has no active subscription or device limit unlimited")

    devices = await remnawave.delete_device(
        user_uuid=current_subscription.user_remna_id,
        hwid=full_hwid,
    )
    logger.info(f"{user.log} Deleted device '{full_hwid}'")

    if devices:
        return

    await dialog_manager.switch_to(state=MainMenu.MAIN)


@inject
async def show_reason(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    subscription_dao: FromDishka[SubscriptionDao],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription = await subscription_dao.get_current(user.telegram_id)

    if subscription:
        kwargs = {
            "status": subscription.current_status,
            "is_trial": subscription.is_trial,
            "traffic_strategy": subscription.traffic_limit_strategy,
            "reset_time": i18n_format_expire_time(
                get_traffic_reset_delta(subscription.traffic_limit_strategy)
            ),
        }
    else:
        kwargs = {"status": False}

    await callback.answer(
        text=i18n.get("ntf-common.connect-not-available", **kwargs),
        show_alert=True,
    )


@inject
async def on_show_qr(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    bot_service: FromDishka[BotService],
    generate_referral_qr: FromDishka[GenerateReferralQr],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    referral_url = await bot_service.get_referral_url(user.referral_code)
    referral_qr = await generate_referral_qr.system(referral_url)

    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(
            i18n_key="",
            media=MediaDescriptorDto(kind="bytes", value=referral_qr, filename="qr.png"),
            media_type=MediaType.PHOTO,
            disable_default_markup=False,
            delete_after=None,
        ),
    )


@inject
async def on_withdraw_points(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(text=i18n.get("ntf-common.withdraw-points"), show_alert=True)


@inject
async def on_invite(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
) -> None:
    settings = await settings_dao.get()
    if settings.referral.enable:
        await dialog_manager.switch_to(state=MainMenu.INVITE)
    return
