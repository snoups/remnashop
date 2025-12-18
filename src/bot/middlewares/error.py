import traceback
from typing import Any, Awaitable, Callable, Optional, cast

from aiogram.types import ErrorEvent, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram.utils.formatting import Text
from dishka import AsyncContainer

from src.bot.keyboards import get_user_keyboard
from src.core.constants import CONTAINER_KEY
from src.core.enums import MiddlewareEventType
from src.core.exceptions import MenuRenderingError
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.notification import NotificationService
from src.services.user import UserService

from .base import EventTypedMiddleware


class ErrorMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.ERROR]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(event)

        error_event = cast(ErrorEvent, event)
        error = error_event.exception
        traceback_str = traceback.format_exc()
        error_type_name = type(error).__name__
        error_message = Text(str(error)[:512])

        container: AsyncContainer = data[CONTAINER_KEY]
        notification_service: NotificationService = await container.get(NotificationService)

        if aiogram_user:
            reply_markup = get_user_keyboard(aiogram_user.id)
            user_service: UserService = await container.get(UserService)
            user: Optional[UserDto] = await user_service.get(telegram_id=aiogram_user.id)

            if user and not user.is_dev and not isinstance(error, MenuRenderingError):
                await redirect_to_main_menu_task.kiq(aiogram_user.id)
        else:
            user = None
            reply_markup = None

        await notification_service.error_notify(
            error_id=user.telegram_id if user else error_event.update.update_id,
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": True if user else False,
                    "user_id": str(user.telegram_id) if user else False,
                    "user_name": user.name if user else False,
                    "username": user.username if user else False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                reply_markup=reply_markup,
            ),
        )
