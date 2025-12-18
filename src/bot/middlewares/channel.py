import traceback
from typing import Any, Awaitable, Callable, Union

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.utils.formatting import Text
from dishka import AsyncContainer
from loguru import logger

from src.bot.keyboards import CALLBACK_CHANNEL_CONFIRM, get_channel_keyboard, get_user_keyboard
from src.core.constants import CONTAINER_KEY, USER_KEY
from src.core.enums import MiddlewareEventType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.settings import SettingsService

from .base import EventTypedMiddleware

ALLOWED_STATUSES = (
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
)


class ChannelMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.MESSAGE, MiddlewareEventType.CALLBACK_QUERY]

    async def middleware_logic(  # noqa: C901
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        container: AsyncContainer = data[CONTAINER_KEY]
        user: UserDto = data[USER_KEY]
        settings_service: SettingsService = await container.get(SettingsService)

        if not await settings_service.is_channel_required():
            return await handler(event, data)

        if user.is_privileged:
            logger.debug(f"User '{user.telegram_id}' skipped channel check (privileged)")
            return await handler(event, data)

        bot: Bot = await container.get(Bot)
        notification_service: NotificationService = await container.get(NotificationService)

        settings = await settings_service.get()

        chat_id: Union[str, int, None] = None
        channel_link = settings.channel_link.get_secret_value()
        if settings.channel_has_username:
            chat_id = channel_link
        elif settings.channel_id:
            chat_id = settings.channel_id

        if chat_id is None:
            logger.warning(
                f"User '{user.telegram_id}' skipped channel check: no valid chat_id or username"
            )
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(
                chat_id=chat_id,
                user_id=user.telegram_id,
            )
        except Exception as exception:
            traceback_str = traceback.format_exc()
            error_type_name = type(exception).__name__
            error_message = Text(str(exception)[:512])

            await notification_service.error_notify(
                error_id=user.telegram_id,
                traceback_str=traceback_str,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-error",
                    i18n_kwargs={
                        "user": True,
                        "user_id": str(user.telegram_id),
                        "user_name": user.name,
                        "username": user.username or False,
                        "error": f"{error_type_name}: Skipped channel required '{channel_link}' "
                        + f"check due to error: {error_message.as_html()}",
                    },
                    reply_markup=get_user_keyboard(user.telegram_id),
                ),
            )
            return await handler(event, data)

        if member.status in ALLOWED_STATUSES:
            if self._is_click_confirm(event):
                await self._delete_channel_message(event)

            logger.debug(f"User '{user.telegram_id}' passed channel check. Status: {member.status}")
            # TODO: Auto confirming
            return await handler(event, data)

        if self._is_click_confirm(event):
            await self._delete_channel_message(event)
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(
                    i18n_key="ntf-channel-join-error",
                    reply_markup=get_channel_keyboard(settings.get_url_channel_link),
                    auto_delete_after=None,
                    add_close_button=False,
                ),
            )
            logger.debug(f"User '{user.telegram_id}' failed channel check")
            return

        if member.status == ChatMemberStatus.LEFT:
            i18n_key = "ntf-channel-join-required-left"
        else:
            i18n_key = "ntf-channel-join-required"

        logger.debug(f"User '{user.telegram_id}' is not subscribed to channel")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=i18n_key,
                reply_markup=get_channel_keyboard(settings.get_url_channel_link),
                auto_delete_after=None,
                add_close_button=False,
            ),
        )
        return

    def _is_click_confirm(self, event: TelegramObject) -> bool:
        return isinstance(event, CallbackQuery) and event.data == CALLBACK_CHANNEL_CONFIRM

    async def _delete_channel_message(self, event: TelegramObject) -> None:
        if not isinstance(event, CallbackQuery):
            return

        if event.message is not None and isinstance(event.message, Message):
            await event.message.delete()
