from typing import Final

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from loguru import logger

from app.core.constants import USER_KEY
from app.core.exceptions import CooldownError, NotFoundError, ValidationError
from app.modules.subscriptions import (
    ActivateTrialSubscriptionDto,
    ActivateTrialSubscriptionUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceDto,
    DeleteDeviceUseCase,
    GetAvailableTrialUseCase,
    ReissueSubscriptionUseCase,
)
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu

_DEFAULT_TRIAL_DURATION_DAYS: Final[int] = 3

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

    plan = result.plan
    duration_days = plan.durations[0].days if plan.durations else _DEFAULT_TRIAL_DURATION_DAYS

    try:
        await activate_trial_subscription(
            user, ActivateTrialSubscriptionDto(plan=plan, duration_days=duration_days)
        )
    except (NotFoundError, ValidationError):
        logger.exception(f"{user.log} Trial activation failed")
        await callback.answer(runner.get("ntf-common.trial-unavailable"), show_alert=True)
        return

    await dialog_manager.switch_to(state=MainMenu.MAIN)


async def on_device_delete_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    selected_index = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    hwid_map = dialog_manager.dialog_data.get("hwid_map", [])
    device = hwid_map[selected_index] if selected_index < len(hwid_map) else None
    if not device:
        return
    dialog_manager.dialog_data["selected_hwid"] = device["hwid"]
    await dialog_manager.switch_to(state=MainMenu.DEVICE_CONFIRM_DELETE)


@inject
async def on_device_delete_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    delete_device: FromDishka[DeleteDeviceUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    hwid = dialog_manager.dialog_data.get("selected_hwid")
    if not hwid:
        return
    runner = get_translator(i18n, user)
    try:
        await delete_device(user, DeleteDeviceDto(hwid=hwid))
    except CooldownError as e:
        await callback.answer(
            runner.get("ntf-common.cooldown-active", available_at=str(e.available_at)),
            show_alert=True,
        )
        return
    await callback.answer(runner.get("ntf-devices.deleted"))
    await dialog_manager.switch_to(state=MainMenu.DEVICES)


@inject
async def on_device_delete_all_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    delete_all_devices: FromDishka[DeleteAllDevicesUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    try:
        await delete_all_devices(user)
    except CooldownError as e:
        await callback.answer(
            runner.get("ntf-common.cooldown-active", available_at=str(e.available_at)),
            show_alert=True,
        )
        return
    await callback.answer(runner.get("ntf-devices.all-deleted"))
    await dialog_manager.switch_to(state=MainMenu.DEVICES)


@inject
async def on_reissue_subscription_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    reissue_subscription: FromDishka[ReissueSubscriptionUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    try:
        await reissue_subscription(user)
    except CooldownError as e:
        await callback.answer(
            runner.get("ntf-common.cooldown-active", available_at=str(e.available_at)),
            show_alert=True,
        )
        return
    await callback.answer(runner.get("ntf-devices.reissued"))
    await dialog_manager.switch_to(state=MainMenu.DEVICES)
