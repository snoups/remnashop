from typing import Any, Awaitable, Callable, Final, Optional, cast

from aiogram.types import Message, TelegramObject
from dishka import AsyncContainer

from app.core.constants import CONTAINER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.settings import BOT_COMMANDS, GetBotCommandsDto, GetBotCommandsUseCase
from app.telegram.middlewares.base import EventTypedMiddleware

_CURRENT_COMMAND_NAMES: Final[frozenset[str]] = frozenset(item.command for item in BOT_COMMANDS)


def _parse_command(text: Optional[str]) -> Optional[str]:
    if not text or not text.startswith("/"):
        return None
    first_token = text.split(maxsplit=1)[0]
    name = first_token[1:].split("@", 1)[0].lower()
    return name or None


class CommandGateMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.MESSAGE]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = cast(Message, event)
        command = _parse_command(message.text)

        if command in _CURRENT_COMMAND_NAMES:
            container: AsyncContainer = data[CONTAINER_KEY]
            use_case = await container.get(GetBotCommandsUseCase)
            commands = await use_case.system(GetBotCommandsDto())
            disabled = {item.command for item in commands if not item.enabled}
            if command in disabled:
                return None

        return await handler(event, data)
