from typing import Any, Awaitable, Callable

from aiogram.enums import ChatType
from aiogram.types import Chat, TelegramObject
from dishka import AsyncContainer

from app.core.config import AppConfig
from app.core.constants import CONFIG_KEY, CONTAINER_KEY, USER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.users import RegisterTelegramUserDto, RegisterTelegramUserUseCase
from app.telegram.middlewares.base import EventTypedMiddleware


class UserMiddleware(EventTypedMiddleware):
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
        # PrivateFilter is a root filter, evaluated *inside* aiogram's outer-
        # middleware wrapping -- this middleware would otherwise run its DB
        # write for group-chat senders before PrivateFilter ever rejects the
        # event. Gate on event_chat here instead of relying on the filter.
        chat = data.get("event_chat")
        if not isinstance(chat, Chat) or chat.type != ChatType.PRIVATE:
            return await handler(event, data)

        aiogram_user = self._get_aiogram_user(data)

        if aiogram_user is None or aiogram_user.is_bot:
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        config: AppConfig = data[CONFIG_KEY]
        use_case = await container.get(RegisterTelegramUserUseCase)

        data[USER_KEY] = await use_case.system(
            RegisterTelegramUserDto(
                telegram_id=aiogram_user.id,
                name=aiogram_user.full_name,
                language=config.default_locale,
            )
        )
        return await handler(event, data)
