from typing import Any, Awaitable, Callable, Optional

from aiogram.types import CallbackQuery, Message, TelegramObject
from dishka import AsyncContainer
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.middlewares.base import EventTypedMiddleware


class BlacklistMiddleware(EventTypedMiddleware):
    __event_types__ = [
        MiddlewareEventType.MESSAGE,
        MiddlewareEventType.CALLBACK_QUERY,
    ]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: Optional[UserDto] = data.get(USER_KEY)
        if user is None or not user.is_blocked:
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        i18n: TranslatorHub = await container.get(TranslatorHub)
        runner = get_translator(i18n, user)
        text = runner.get("ntf-common.access-restricted")

        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        return None
