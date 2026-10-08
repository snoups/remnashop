from typing import Any, Awaitable, Callable, Final, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from dishka import AsyncContainer
from fluentogram import TranslatorHub, TranslatorRunner
from loguru import logger
from redis.asyncio import Redis

from app.core.constants import CONTAINER_KEY, REDIS_KEY_PREFIX, USER_KEY
from app.core.enums import MiddlewareEventType
from app.modules.settings import BotRequirementsDto, GetBotRequirementsUseCase
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.middlewares.base import EventTypedMiddleware

# here, not under routers/: importing app.telegram.routers pulls in the handlers,
# which import this module
RULES_ACCEPT_CALLBACK: Final[str] = "requirements:rules"
CHANNEL_CHECK_CALLBACK: Final[str] = "requirements:channel"

_SUBSCRIBED_TTL_S: Final[int] = 5 * 60
_LEFT_STATUSES: Final[frozenset[str]] = frozenset({"left", "kicked"})
_REQUIREMENT_CALLBACKS: Final[frozenset[str]] = frozenset(
    {RULES_ACCEPT_CALLBACK, CHANNEL_CHECK_CALLBACK}
)


def channel_member_key(channel_id: int, telegram_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}channel_member:{channel_id}:{telegram_id}"


async def is_channel_member(bot: Bot, redis: Redis, channel_id: int, telegram_id: int) -> bool:
    if await redis.exists(channel_member_key(channel_id, telegram_id)):
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=telegram_id)
    except TelegramAPIError as error:
        # a broken channel setup must not lock every customer out
        logger.warning(f"Channel {channel_id} membership check failed: {error}")
        return True
    if member.status in _LEFT_STATUSES:
        return False
    await redis.set(channel_member_key(channel_id, telegram_id), "1", ex=_SUBSCRIBED_TTL_S)
    return True


class RequirementsMiddleware(EventTypedMiddleware):
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
        if user is None or user.is_privileged:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data in _REQUIREMENT_CALLBACKS:
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        requirements = await (await container.get(GetBotRequirementsUseCase)).system()
        runner = get_translator(await container.get(TranslatorHub), user)

        if requirements.rules_required and user.rules_accepted_at is None:
            await ask_requirement(
                event, runner.get("ntf-requirements.rules"), _rules_keyboard(runner, requirements)
            )
            return None

        channel_id = requirements.channel_id
        if (
            requirements.channel_required
            and channel_id is not None
            and user.telegram_id is not None
        ):
            redis = await container.get(Redis)
            if not await is_channel_member(data["bot"], redis, channel_id, user.telegram_id):
                await ask_requirement(
                    event,
                    runner.get("ntf-requirements.channel"),
                    channel_keyboard(runner, requirements),
                )
                return None

        return await handler(event, data)


async def ask_requirement(event: TelegramObject, text: str, keyboard: InlineKeyboardMarkup) -> None:
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard)
    elif isinstance(event, CallbackQuery):
        if event.message is None:
            await event.answer(text, show_alert=True)
            return
        await event.message.answer(text, reply_markup=keyboard)
        await event.answer()


def _rules_keyboard(
    runner: TranslatorRunner, requirements: BotRequirementsDto
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=runner.get("btn-requirements.rules"), url=requirements.rules_url
                )
            ],
            [
                InlineKeyboardButton(
                    text=runner.get("btn-requirements.accept"), callback_data=RULES_ACCEPT_CALLBACK
                )
            ],
        ]
    )


def channel_keyboard(
    runner: TranslatorRunner, requirements: BotRequirementsDto
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=runner.get("btn-requirements.subscribe"), url=requirements.channel_url
                )
            ],
            [
                InlineKeyboardButton(
                    text=runner.get("btn-requirements.check"), callback_data=CHANNEL_CHECK_CALLBACK
                )
            ],
        ]
    )
