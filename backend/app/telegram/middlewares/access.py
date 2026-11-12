from typing import Any, Awaitable, Callable, Optional

from aiogram.types import TelegramObject
from dishka import AsyncContainer
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.access import is_restricted_for
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.middlewares.base import EventTypedMiddleware, is_successful_payment
from app.telegram.notice import answer_notice


class AccessMiddleware(EventTypedMiddleware):
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
        if user is None or is_successful_payment(event):
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        get_settings = await container.get(GetAccessSettingsUseCase)
        if not is_restricted_for(user, await get_settings.system()):
            return await handler(event, data)

        text = get_translator(await container.get(TranslatorHub), user).get("ntf-access.restricted")
        await answer_notice(event, text)
        return None
