from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.core.constants import USER_KEY
from src.core.enums import SystemNotificationType, UserNotificationType
from src.core.utils.formatters import format_log_user
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService


@inject
async def on_user_type_selected(
    callback: CallbackQuery,
    widget: Select[UserNotificationType],
    dialog_manager: DialogManager,
    selected_type: UserNotificationType,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await notification_service.get_user_settings()
    # TODO: UserNotificationType


@inject
async def on_system_type_selected(
    callback: CallbackQuery,
    widget: Select[SystemNotificationType],
    dialog_manager: DialogManager,
    selected_type: SystemNotificationType,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await notification_service.get_system_settings()
    new_value = settings.toggle_notification(selected_type)
    await notification_service.set_system_settings(settings)

    logger.info(
        f"{format_log_user(user)} Change notification type: '{selected_type}' to '{new_value}'"
    )
