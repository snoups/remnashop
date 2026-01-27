from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.dto import UserDto
from src.application.use_cases.settings import (
    ChangeAccessMode,
    ToggleConditionRequirement,
    TogglePayments,
    ToggleRegistration,
    UpdateChannelRequirement,
    UpdateRulesRequirement,
)
from src.core.constants import USER_KEY
from src.core.enums import AccessMode, AccessRequirements
from src.telegram.states import DashboardAccess


@inject
async def on_access_mode_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_mode: AccessMode,
    change_access_mode: FromDishka[ChangeAccessMode],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await change_access_mode(user, selected_mode)


@inject
async def on_payments_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_payments: FromDishka[TogglePayments],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_payments(user)


@inject
async def on_registration_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_registration: FromDishka[ToggleRegistration],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_registration(user)


@inject
async def on_condition_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_condition_requirement: FromDishka[ToggleConditionRequirement],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_condition_requirement(user, AccessRequirements(callback.data or ""))


@inject
async def on_rules_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    update_rules_requirement: FromDishka[UpdateRulesRequirement],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if await update_rules_requirement(user, message.text or ""):
        await dialog_manager.switch_to(state=DashboardAccess.CONDITIONS)


@inject
async def on_channel_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    update_channel_requirement: FromDishka[UpdateChannelRequirement],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await update_channel_requirement(user, message.text or "")
