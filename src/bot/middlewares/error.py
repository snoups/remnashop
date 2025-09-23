import traceback
from typing import Any, Awaitable, Callable, Optional, cast

from aiogram.types import ErrorEvent, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram.utils.formatting import Text
from loguru import logger

from src.core.enums import MiddlewareEventType
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task

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
        user_id = str(aiogram_user.id) if aiogram_user else None
        user_name = aiogram_user.full_name if aiogram_user else None
        error_event = cast(ErrorEvent, event)

        logger.exception(f"Update: {error_event.update}\nException: {error_event.exception}")

        traceback_str = traceback.format_exc()
        error_type_name = type(error_event.exception).__name__
        error_message = Text(str(error_event.exception)[:512])

        await send_error_notification_task.kiq(
            update_id=error_event.update.update_id,
            traceback_str=traceback_str,
            i18n_kwargs={
                "user": bool(user_id),
                "id": user_id,
                "name": user_name,
                "error": f"{error_type_name}: {error_message.as_html()}",
            },
        )

        return await handler(event, data)
