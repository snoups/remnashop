from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, ClassVar, Final, Optional

from aiogram import BaseMiddleware, Router
from aiogram.types import ErrorEvent, TelegramObject
from aiogram.types import User as AiogramUser
from loguru import logger

from src.core.enums import MiddlewareEventType

DEFAULT_UPDATE_TYPES: Final[list[MiddlewareEventType]] = [
    MiddlewareEventType.MESSAGE,
    MiddlewareEventType.CALLBACK_QUERY,
]


class EventTypedMiddleware(BaseMiddleware, ABC):
    __event_types__: ClassVar[list[MiddlewareEventType]] = DEFAULT_UPDATE_TYPES

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await self.middleware_logic(handler, event, data)
        return result

    def setup_inner(self, router: Router) -> None:
        for event_type in self.__event_types__:
            router.observers[event_type].middleware(self)

        logger.debug(
            f"{self.__class__.__name__} set as INNER for: "
            f"{', '.join(t.value for t in self.__event_types__)}"
        )

    def setup_outer(self, router: Router) -> None:
        for event_type in self.__event_types__:
            router.observers[event_type].outer_middleware(self)

            logger.debug(
                f"{self.__class__.__name__} set as OUTER for: "
                f"{', '.join(t.value for t in self.__event_types__)}"
            )

    @abstractmethod
    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any: ...  # TODO: Implement checking performance

    @staticmethod
    def _get_aiogram_user(event: TelegramObject) -> Optional[AiogramUser]:
        if hasattr(event, "from_user"):
            return event.from_user  # type: ignore[no-any-return]
        elif isinstance(event, ErrorEvent):
            if event.update.callback_query:
                return event.update.callback_query.from_user
            elif event.update.message:
                return event.update.message.from_user
        return None
