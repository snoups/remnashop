import time
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, ClassVar, Final, Optional

from aiogram import BaseMiddleware, Router
from aiogram.types import TelegramObject
from aiogram.types import User as AiogramUser
from loguru import logger

from app.core.enums import MiddlewareEventType

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
        start = time.perf_counter()
        result = await self.middleware_logic(handler, event, data)
        logger.debug(
            f"Middleware '{self.__class__.__name__}' executed in {time.perf_counter() - start:.4f}s"
        )
        return result

    def setup_outer(self, router: Router) -> None:
        for event_type in self.__event_types__:
            router.observers[event_type].outer_middleware(self)

    def setup_inner(self, router: Router) -> None:
        for event_type in self.__event_types__:
            router.observers[event_type].middleware(self)

    @abstractmethod
    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any: ...

    def _get_aiogram_user(self, data: dict[str, Any]) -> Optional[AiogramUser]:
        user = data.get("event_from_user")
        return user if isinstance(user, AiogramUser) else None
