import asyncio
from enum import auto
from typing import Final, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from loguru import logger

from app.core.enums import UpperStrEnum
from app.core.telegram_api import BOT_API_ERRORS, bot_api_error_text, bot_client

# an alert waits out a short flood-wait once; a long one fails the delivery
_MAX_RETRY_AFTER_S: Final[float] = 30.0
TELEGRAM_TIMEOUT_SECONDS: Final[float] = 10.0
# a 400, not a 403: a deleted account or an id Telegram never gave this bot
_CHAT_NOT_FOUND: Final[str] = "chat not found"


class TelegramSendResult(UpperStrEnum):
    SENT = auto()
    # never pressed /start, blocked the bot or the account is gone: retrying won't help
    FORBIDDEN = auto()
    FAILED = auto()


async def _send_with_retry(
    bot: Bot, chat_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup]
) -> None:
    # plain text: logins and error messages in the payload are user-controlled
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    except TelegramRetryAfter as error:
        if error.retry_after > _MAX_RETRY_AFTER_S:
            raise
        await asyncio.sleep(error.retry_after)
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


async def send_telegram_text(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
    *,
    bot: Optional[Bot] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> TelegramSendResult:
    try:
        if bot is None:
            async with bot_client(token, proxy, timeout=TELEGRAM_TIMEOUT_SECONDS) as own_bot:
                await _send_with_retry(own_bot, chat_id, text, reply_markup)
        else:
            await _send_with_retry(bot, chat_id, text, reply_markup)
    except TelegramForbiddenError as error:
        logger.info(f"Telegram notification to {chat_id} refused: {error.message}")
        return TelegramSendResult.FORBIDDEN
    except TelegramBadRequest as error:
        if _CHAT_NOT_FOUND not in error.message.lower():
            logger.warning(
                f"Telegram notification to {chat_id} failed: {bot_api_error_text(error)}"
            )
            return TelegramSendResult.FAILED
        logger.info(f"Telegram notification to {chat_id} refused: {error.message}")
        return TelegramSendResult.FORBIDDEN
    except BOT_API_ERRORS as error:
        logger.warning(f"Telegram notification to {chat_id} failed: {bot_api_error_text(error)}")
        return TelegramSendResult.FAILED
    return TelegramSendResult.SENT


async def send_telegram_message(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
    *,
    bot: Optional[Bot] = None,
) -> bool:
    result = await send_telegram_text(token, proxy, chat_id, text, bot=bot)
    return result is TelegramSendResult.SENT
