from aiogram.types import ErrorEvent
from aiogram_dialog import DialogManager
from dishka import FromDishka
from loguru import logger

from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService

# Registered in main router (src/bot/dispatcher.py)


async def on_unknown_state(
    event: ErrorEvent,
    user: UserDto,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    logger.error(f"{log(user)} Unknown state")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-error-dialog-unknown"),
    )


async def on_unknown_intent(
    event: ErrorEvent,
    user: UserDto,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    logger.error(f"{log(user)} Unknown intent")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-error-dialog-unknown"),
    )
