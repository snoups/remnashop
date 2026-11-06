import asyncio
from enum import auto
from http import HTTPStatus
from typing import Any, Final, Optional

from loguru import logger

from app.core.enums import UpperStrEnum
from app.core.telegram_api import (
    BOT_API_ERRORS,
    BotApi,
    BotApiRefusedError,
    bot_api_error_text,
    bot_client,
)

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
    bot: BotApi, chat_id: int, text: str, reply_markup: Optional[dict[str, Any]]
) -> None:
    # plain text: logins and error messages in the payload are user-controlled
    try:
        await bot.call("sendMessage", chat_id=chat_id, text=text, reply_markup=reply_markup)
    except BotApiRefusedError as error:
        retry_after = error.retry_after
        if retry_after is None or retry_after > _MAX_RETRY_AFTER_S:
            raise
        await asyncio.sleep(retry_after)
        await bot.call("sendMessage", chat_id=chat_id, text=text, reply_markup=reply_markup)


async def send_telegram_text(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[dict[str, Any]] = None,
) -> TelegramSendResult:
    try:
        async with bot_client(token, proxy, timeout=TELEGRAM_TIMEOUT_SECONDS) as bot:
            await _send_with_retry(bot, chat_id, text, reply_markup)
    except BotApiRefusedError as error:
        if error.error_code == HTTPStatus.FORBIDDEN or (
            error.error_code == HTTPStatus.BAD_REQUEST
            and _CHAT_NOT_FOUND in error.description.lower()
        ):
            logger.info(f"Telegram notification to {chat_id} refused: {error.description}")
            return TelegramSendResult.FORBIDDEN
        logger.warning(f"Telegram notification to {chat_id} failed: {error.description}")
        return TelegramSendResult.FAILED
    except BOT_API_ERRORS as error:
        logger.warning(f"Telegram notification to {chat_id} failed: {bot_api_error_text(error)}")
        return TelegramSendResult.FAILED
    return TelegramSendResult.SENT


async def send_telegram_message(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
) -> bool:
    result = await send_telegram_text(token, proxy, chat_id, text)
    return result is TelegramSendResult.SENT
