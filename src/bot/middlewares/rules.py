from typing import Any, Awaitable, Callable, Optional

from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as AiogramUser
from dishka import AsyncContainer
from loguru import logger

from src.bot.keyboards import CALLBACK_RULES_ACCEPT, get_rules_keyboard
from src.core.config import AppConfig
from src.core.constants import CONTAINER_KEY
from src.core.enums import MiddlewareEventType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.settings import SettingsService
from src.services.user import UserService

from .base import EventTypedMiddleware


class RulesMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.MESSAGE, MiddlewareEventType.CALLBACK_QUERY]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(event)

        if aiogram_user is None or aiogram_user.is_bot:
            logger.warning("Terminating middleware: event from bot or missing user")
            return

        container: AsyncContainer = data[CONTAINER_KEY]
        settings_service: SettingsService = await container.get(SettingsService)

        if not await settings_service.is_rules_required():
            return await handler(event, data)

        config: AppConfig = await container.get(AppConfig)
        notification_service: NotificationService = await container.get(NotificationService)
        user_service: UserService = await container.get(UserService)

        settings = await settings_service.get()
        user: Optional[UserDto] = await user_service.get(telegram_id=aiogram_user.id)

        fake_user = UserDto(
            telegram_id=aiogram_user.id,
            username=aiogram_user.username,
            name=aiogram_user.full_name,
            language=(
                aiogram_user.language_code
                if aiogram_user.language_code in config.locales
                else config.default_locale
            ),
        )

        if self._is_click_accept(event):
            await self._delete_rules_message(event)
            return await handler(event, data)

        if user is None:
            await notification_service.notify_user(
                user=fake_user,
                payload=MessagePayload(
                    i18n_key="ntf-rules-accept-required",
                    i18n_kwargs={"url": settings.rules_link.get_secret_value()},
                    reply_markup=get_rules_keyboard(),
                    auto_delete_after=None,
                    add_close_button=False,
                ),
            )
            return

        return await handler(event, data)

    def _is_click_accept(self, event: TelegramObject) -> bool:
        return isinstance(event, CallbackQuery) and event.data == CALLBACK_RULES_ACCEPT

    async def _delete_rules_message(self, event: TelegramObject) -> None:
        if not isinstance(event, CallbackQuery):
            return

        if event.message is not None and isinstance(event.message, Message):
            await event.message.delete()
