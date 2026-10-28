from typing import Any, Awaitable, Callable, Final, Optional

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
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
from app.core.enums import MiddlewareEventType, PurchaseChannel
from app.modules.legal import GetPendingLegalDocumentsUseCase
from app.modules.settings import (
    BotRequirementsDto,
    BotStatusKind,
    GetBotRequirementsUseCase,
    ReportBotStatusDto,
    ReportBotStatusUseCase,
)
from app.modules.users import UserDto
from app.telegram.broadcast_callbacks import RESUBSCRIBE_CALLBACK, UNSUBSCRIBE_CALLBACK
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import get_translator
from app.telegram.legal_gate import (
    GATE_MESSAGE_TTL_S,
    LEGAL_GATE_CALLBACK_PREFIXES,
    gate_message_key,
    legal_gate_keyboard,
)
from app.telegram.middlewares.base import EventTypedMiddleware, is_successful_payment

# here, not under routers/: importing app.telegram.routers pulls in the handlers,
# which import this module
CHANNEL_CHECK_CALLBACK: Final[str] = "requirements:channel"

_SUBSCRIBED_TTL_S: Final[int] = 5 * 60
_LEFT_STATUSES: Final[frozenset[str]] = frozenset({"left", "kicked"})
# opting out of marketing must work even before the requirements are met
_REQUIREMENT_CALLBACKS: Final[frozenset[str]] = frozenset(
    {CHANNEL_CHECK_CALLBACK, UNSUBSCRIBE_CALLBACK, RESUBSCRIBE_CALLBACK}
)


def channel_member_key(channel_id: int, telegram_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}channel_member:{channel_id}:{telegram_id}"


async def is_channel_member(
    bot: Bot,
    redis: Redis,
    channel_id: int,
    telegram_id: int,
    report: ReportBotStatusUseCase,
) -> bool:
    if await redis.exists(channel_member_key(channel_id, telegram_id)):
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=telegram_id)
    except TelegramNetworkError as error:
        # Telegram unreachable for a moment: the channel setup itself is fine
        logger.warning(f"Channel {channel_id} membership check skipped: {error}")
        return True
    except TelegramAPIError as error:
        # a broken channel setup must not lock every customer out
        logger.warning(f"Channel {channel_id} membership check failed: {error}")
        try:
            await report.system(
                ReportBotStatusDto(
                    kind=BotStatusKind.CHANNEL_CHECK_FAILED,
                    detail=str(error),
                    channel_id=channel_id,
                )
            )
        except Exception:
            logger.exception(f"Failed to report the channel {channel_id} check failure")
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
        if user is None or user.is_privileged or is_successful_payment(event):
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and (
            event.data in _REQUIREMENT_CALLBACKS
            or (event.data or "").startswith(LEGAL_GATE_CALLBACK_PREFIXES)
        ):
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        runner = get_translator(await container.get(TranslatorHub), user)

        pending = await (await container.get(GetPendingLegalDocumentsUseCase)).execute(
            user, PurchaseChannel.BOT, user.language
        )
        if pending.documents:
            await _remember_stopped(event, user, await container.get(Redis))
            await ask_requirement(
                event,
                render_window_text(
                    runner, "msg-legal-gate-update" if pending.is_update else "msg-legal-gate"
                ),
                legal_gate_keyboard(runner, pending),
                parse_mode=ParseMode.HTML,
            )
            return None

        requirements = await (await container.get(GetBotRequirementsUseCase)).system()

        channel_id = requirements.channel_id
        if (
            requirements.channel_required
            and channel_id is not None
            and user.telegram_id is not None
        ):
            redis = await container.get(Redis)
            report = await container.get(ReportBotStatusUseCase)
            if not await is_channel_member(
                data["bot"], redis, channel_id, user.telegram_id, report
            ):
                await _remember_stopped(event, user, redis)
                await ask_requirement(
                    event,
                    runner.get("ntf-requirements.channel"),
                    channel_keyboard(runner, requirements),
                )
                return None

        return await handler(event, data)


async def _remember_stopped(event: TelegramObject, user: UserDto, redis: Redis) -> None:
    if isinstance(event, Message):
        await redis.set(gate_message_key(user.id), event.model_dump_json(), ex=GATE_MESSAGE_TTL_S)


async def ask_requirement(
    event: TelegramObject,
    text: str,
    keyboard: InlineKeyboardMarkup,
    parse_mode: Optional[str] = None,
) -> None:
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
    elif isinstance(event, CallbackQuery):
        if event.message is None:
            await event.answer(text, show_alert=True)
            return
        await event.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
        await event.answer()


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
