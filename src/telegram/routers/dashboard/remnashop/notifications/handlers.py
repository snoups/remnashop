from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.dto import UserDto
from src.application.use_cases.settings import ToggleNotification
from src.core.constants import USER_KEY
from src.core.enums import SystemNotificationType, UserNotificationType


@inject
async def on_user_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: UserNotificationType,
    toggle_notification: FromDishka[ToggleNotification],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_notification(user, selected_type)


@inject
async def on_system_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: SystemNotificationType,
    toggle_notification: FromDishka[ToggleNotification],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_notification(user, selected_type)
