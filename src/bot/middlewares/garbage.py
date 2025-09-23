from typing import Any, Awaitable, Callable, cast

from aiogram.types import Message, TelegramObject
from loguru import logger

from src.core.constants import USER_KEY
from src.core.enums import Command, MiddlewareEventType
from src.core.utils.formatters import format_log_user
from src.infrastructure.database.models.dto import UserDto

from .base import EventTypedMiddleware


class GarbageMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.MESSAGE]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = cast(Message, event)
        user: UserDto = data[USER_KEY]

        if message.text != f"/{Command.START.value.command}":
            await message.delete()
            logger.debug(f"{format_log_user(user)} Message deleted")

        return await handler(event, data)
