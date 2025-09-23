from typing import Any, Awaitable, Callable, Optional

from aiogram.types import TelegramObject
from aiogram.types import User as AiogramUser
from aiogram_dialog.api.internal import FakeUser
from dishka import AsyncContainer
from loguru import logger

from src.core.constants import CONTAINER_KEY, USER_KEY
from src.core.enums import MiddlewareEventType, SystemNotificationType
from src.core.utils.formatters import format_log_user
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.user import UserService

from .base import EventTypedMiddleware


class UserMiddleware(EventTypedMiddleware):
    __event_types__ = [
        MiddlewareEventType.MESSAGE,
        MiddlewareEventType.CALLBACK_QUERY,
        MiddlewareEventType.ERROR,
        MiddlewareEventType.AIOGD_UPDATE,
        MiddlewareEventType.MY_CHAT_MEMBER,
        MiddlewareEventType.PRE_CHECKOUT_QUERY,
    ]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(event)

        if aiogram_user is None or aiogram_user.is_bot:
            logger.warning("Terminating: event from bot or missing user")
            return

        container: AsyncContainer = data[CONTAINER_KEY]
        notification_service: NotificationService = await container.get(NotificationService)
        user_service: UserService = await container.get(UserService)
        user: Optional[UserDto] = await user_service.get(telegram_id=aiogram_user.id)

        if user is None:
            user = await user_service.create(aiogram_user)
            logger.info(f"{format_log_user(user)} Created new user")
            await notification_service.system_notify(
                payload=MessagePayload(
                    i18n_key="ntf-event-new-user",
                    i18n_kwargs={
                        "id": str(user.telegram_id),
                        "name": user.name,
                        "username": user.username or False,
                    },
                    auto_delete_after=None,
                    add_close_button=True,
                ),
                ntf_type=SystemNotificationType.USER_REGISTERED,
            )
        elif not isinstance(aiogram_user, FakeUser):
            await user_service.compare_and_update(user, aiogram_user)

        await user_service.update_recent_activity(telegram_id=user.telegram_id)
        data[USER_KEY] = user

        return await handler(event, data)
