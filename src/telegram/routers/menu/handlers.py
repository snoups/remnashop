import base64
import hashlib
import secrets
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier, TranslatorRunner
from src.application.common.dao import SettingsDao, SubscriptionDao, UserDao
from src.application.common.uow import UnitOfWork
from src.application.dto import MediaDescriptorDto, MessagePayloadDto, PlanSnapshotDto, UserDto
from src.application.services import BotService
from src.application.use_cases.referral.queries.code import GenerateReferralQr
from src.application.use_cases.remnawave.commands.management import (
    DeleteUserAllDevices,
    DeleteUserDevice,
    DeleteUserDeviceDto,
    ReissueSubscription,
)
from src.application.use_cases.subscription.commands.purchase import (
    ActivateTrialSubscription,
    ActivateTrialSubscriptionDto,
)
from src.application.use_cases.user.queries.plans import GetAvailableTrial
from src.core.config import AppConfig
from src.core.constants import USER_KEY, PASSWORD_SCRYPT_DKLEN, PASSWORD_SCRYPT_N, PASSWORD_SCRYPT_P, PASSWORD_SCRYPT_R, WEB_PASSWORD_ALPHABET, WEB_PASSWORD_LEN
from src.core.enums import MediaType
from src.core.utils.i18n_helpers import i18n_format_expire_time
from src.core.utils.time import get_traffic_reset_delta
from src.telegram.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.telegram.states import MainMenu

router = Router(name=__name__)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _hash_password(password: str, key: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password=f"{password}:{key}".encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_SCRYPT_DKLEN,
    )
    return (
        f"scrypt${PASSWORD_SCRYPT_N}${PASSWORD_SCRYPT_R}${PASSWORD_SCRYPT_P}"
        f"${_b64url_encode(salt)}${_b64url_encode(digest)}"
    )


def _generate_web_password() -> str:
    return "".join(secrets.choice(WEB_PASSWORD_ALPHABET) for _ in range(WEB_PASSWORD_LEN))


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
async def on_device_delete_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    selected_short_hwid = dialog_manager.item_id  # type: ignore[attr-defined]
    hwid_map = dialog_manager.dialog_data.get("hwid_map", [])
    device = next((d for d in hwid_map if d["short_hwid"] == selected_short_hwid), None)

    if not device:
        raise ValueError(f"Device not found for hwid '{selected_short_hwid}'")

    dialog_manager.dialog_data["selected_short_hwid"] = selected_short_hwid
    dialog_manager.dialog_data["selected_device_label"] = device["label"]
    await dialog_manager.switch_to(state=MainMenu.DEVICE_CONFIRM_DELETE)


@inject
async def on_device_delete_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    delete_user_device: FromDishka[DeleteUserDevice],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_short_hwid = dialog_manager.dialog_data.get("selected_short_hwid")
    hwid_map = dialog_manager.dialog_data.get("hwid_map", [])

    if not selected_short_hwid or not hwid_map:
        raise ValueError("Missing selected device data")

    full_hwid = next((d["hwid"] for d in hwid_map if d["short_hwid"] == selected_short_hwid), None)
    if not full_hwid:
        raise ValueError(f"Full HWID not found for '{selected_short_hwid}'")

    await delete_user_device(
        user, DeleteUserDeviceDto(telegram_id=user.telegram_id, hwid=full_hwid)
    )
    await notifier.notify_user(user=user, i18n_key="ntf-devices.deleted")
    await dialog_manager.switch_to(state=MainMenu.DEVICES)


@inject
async def on_device_delete_all_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    delete_user_all_devices: FromDishka[DeleteUserAllDevices],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await delete_user_all_devices(user)
    await notifier.notify_user(user=user, i18n_key="ntf-devices.all-deleted")
    await dialog_manager.switch_to(state=MainMenu.DEVICES)


@inject
async def on_reissue_subscription_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    reissue_subscription: FromDishka[ReissueSubscription],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await reissue_subscription(user)
    await notifier.notify_user(user=user, i18n_key="ntf-devices.reissued")
    await dialog_manager.switch_to(state=MainMenu.DEVICES)


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
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await notifier.notify_user(user=user, i18n_key="ntf-common.withdraw-points")


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


@inject
async def on_generate_web_credentials(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    notifier: FromDishka[Notifier],
) -> None:
    if not config.web_enabled:
        raise ValueError("WEB_ENABLED is disabled")

    web_cabinet_url = config.web_cabinet_url.strip()
    if not web_cabinet_url:
        raise ValueError("WEB_CABINET_URL is not configured")

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    db_user = await user_dao.get_by_telegram_id(user.telegram_id)
    if not db_user:
        raise ValueError(f"User '{user.telegram_id}' not found")

    plain_password = _generate_web_password()
    db_user.login = db_user.remna_name
    db_user.password_hash = _hash_password(plain_password, config.crypt_key.get_secret_value())

    async with uow:
        updated = await user_dao.update(db_user)
        if not updated:
            raise ValueError(f"Failed to update user '{user.telegram_id}'")
        await uow.commit()

    await notifier.notify_user(
        user=updated,
        payload=MessagePayloadDto(
            i18n_key="ntf-common.web-cabinet-credentials",
            i18n_kwargs={
                "login": updated.login,
                "password": plain_password,
                "url": web_cabinet_url,
            },
            delete_after=None,
            disable_default_markup=False,
        ),
    )
