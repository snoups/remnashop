from typing import Any, Awaitable, Callable, Optional

from aiogram.types import TelegramObject
from dishka import AsyncContainer
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.middlewares.base import EventTypedMiddleware, is_successful_payment
from app.telegram.notice import answer_notice


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
        if user is None or not user.is_blocked or is_successful_payment(event):
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        i18n: TranslatorHub = await container.get(TranslatorHub)
        runner = get_translator(i18n, user)
        await answer_notice(event, runner.get("ntf-common.access-restricted"))
        return None
