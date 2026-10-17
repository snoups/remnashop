from contextlib import suppress
from typing import Any, Awaitable, Callable, cast

from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, TelegramObject

from app.core.enums import MiddlewareEventType
from app.telegram.middlewares.base import EventTypedMiddleware


class GarbageMiddleware(EventTypedMiddleware):
    """The chat is the bot's menu: what a customer types is removed once a
    handler takes it. /start and payment receipts stay."""

    __event_types__ = [MiddlewareEventType.MESSAGE]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = cast(Message, event)
        if not (message.text or "").startswith("/start") and message.successful_payment is None:
            # older than 48h, or already gone: nothing to tidy
            with suppress(TelegramAPIError):
                await message.delete()
        return await handler(event, data)
