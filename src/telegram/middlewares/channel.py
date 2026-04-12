from typing import Any, Awaitable, Callable

from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, TelegramObject
from dishka import AsyncContainer
from loguru import logger

from src.application.common import Notifier
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.access.queries.requirements import CheckChannelSubscription
from src.core.constants import CONTAINER_KEY, USER_KEY
from src.core.enums import MiddlewareEventType
from src.telegram.keyboards import CALLBACK_CHANNEL_CONFIRM, get_channel_keyboard

from .base import EventTypedMiddleware


class ChannelMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.MESSAGE, MiddlewareEventType.CALLBACK_QUERY]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        container: AsyncContainer = data[CONTAINER_KEY]
        user: UserDto = data[USER_KEY]

        check_channel_subscription = await container.get(CheckChannelSubscription)
        notifier = await container.get(Notifier)

        result = await check_channel_subscription(user)

        if result.is_subscribed:
            if self._is_click_confirm(event):
                logger.info(f"{user.log} Confirmed join channel")
                await self._delete_previous_message(event)

            if not result.error_occurred:
                logger.debug(f"User '{user.telegram_id}' passed channel check")

            return await handler(event, data)

        if self._is_click_confirm(event):
            await self._delete_previous_message(event)
            i18n_key = "ntf-requirement.channel-join-error"
        else:
            i18n_key = (
                "ntf-requirement.channel-join-required-left"
                if result.status == ChatMemberStatus.LEFT
                else "ntf-requirement.channel-join-required"
            )

        logger.debug(
            f"User '{user.telegram_id}' failed channel check with status '{result.status}'"
        )

        await notifier.notify_user(
            user=user,
            payload=MessagePayloadDto(
                i18n_key=i18n_key,
                reply_markup=get_channel_keyboard(result.channel_url),  # type: ignore[arg-type]
                disable_default_markup=True,
                delete_after=None,
            ),
        )
        return

    def _is_click_confirm(self, event: TelegramObject) -> bool:
        return isinstance(event, CallbackQuery) and event.data == CALLBACK_CHANNEL_CONFIRM
