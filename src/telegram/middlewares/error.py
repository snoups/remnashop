from typing import Any, Awaitable, Callable, Optional, cast

from aiogram.types import ErrorEvent as AiogramErrorEvent
from aiogram.types import TelegramObject
from aiogram.types import User as AiogramUser
from aiogram_dialog.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
    UnknownState,
)
from dishka import AsyncContainer
from loguru import logger

from src.application.common import EventPublisher, Notifier
from src.application.dto import TempUserDto
from src.application.events import ErrorEvent
from src.application.use_cases.redirect import RedirectMenu
from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, CONTAINER_KEY
from src.core.enums import MiddlewareEventType
from src.core.exceptions import MenuRenderError, PermissionDeniedError

from .base import EventTypedMiddleware


class ErrorMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.ERROR]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event = cast(AiogramErrorEvent, event)
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(data)
        config: AppConfig = data[CONFIG_KEY]
        container: AsyncContainer = data[CONTAINER_KEY]

        event_publisher = await container.get(EventPublisher)
        notifier = await container.get(Notifier)
        redirect_menu = await container.get(RedirectMenu)

        if aiogram_user:
            if isinstance(event.exception, PermissionDeniedError):
                await notifier.notify_user(
                    TempUserDto.from_aiogram(aiogram_user),
                    i18n_key="ntf-error.permission-denied",
                )
                return

            if not isinstance(event.exception, MenuRenderError):
                await redirect_menu.system(aiogram_user.id)

        if isinstance(
            event.exception,
            (
                InvalidStackIdError,
                OutdatedIntent,
                UnknownIntent,
                UnknownState,
            ),
        ):
            return await handler(event, data)

        error_event = ErrorEvent(
            **config.build.data,
            #
            telegram_id=aiogram_user.id if aiogram_user else None,
            username=aiogram_user.username if aiogram_user else None,
            name=aiogram_user.full_name if aiogram_user else None,
            #
            exception=event.exception,
        )

        await event_publisher.publish(error_event)
        logger.exception(event.exception)
