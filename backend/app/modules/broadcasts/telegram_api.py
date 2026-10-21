from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Any, Final, Optional, Union

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.methods import SendAnimation, SendDocument, SendPhoto, SendVideo, TelegramMethod
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from loguru import logger

from app.core.enums import BroadcastMediaType, UpperStrEnum
from app.core.telegram_api import BOT_API_ERRORS, bot_api_error_text, bot_client

_TIMEOUT_SECONDS: Final[float] = 30.0


class SendOutcome(UpperStrEnum):
    SENT = auto()
    BLOCKED = auto()
    FAILED = auto()
    RETRY = auto()
    UNAUTHORIZED = auto()


@dataclass(frozen=True, kw_only=True)
class OutgoingMedia:
    media_type: BroadcastMediaType
    file_id: Optional[str]
    path: Optional[Path]
    content_type: Optional[str]


@dataclass(frozen=True, kw_only=True)
class SendResult:
    outcome: SendOutcome
    message_id: Optional[int] = None
    file_id: Optional[str] = None
    error: Optional[str] = None
    retry_after: Optional[float] = None


class TelegramClientFactory:
    def open(self, token: str, proxy: Optional[str]) -> AbstractAsyncContextManager[Bot]:
        return bot_client(token, proxy, timeout=_TIMEOUT_SECONDS)


def _failure(error: Exception) -> SendResult:
    text = bot_api_error_text(error)
    if isinstance(error, TelegramRetryAfter):
        return SendResult(outcome=SendOutcome.RETRY, error=text, retry_after=error.retry_after)
    if isinstance(error, TelegramUnauthorizedError):
        return SendResult(outcome=SendOutcome.UNAUTHORIZED, error=text)
    if isinstance(error, TelegramForbiddenError):
        return SendResult(outcome=SendOutcome.BLOCKED, error=text)
    if isinstance(error, TelegramEntityTooLarge):
        return SendResult(outcome=SendOutcome.FAILED, error=text)
    if isinstance(error, (TelegramServerError, TelegramNetworkError)) or not isinstance(
        error, TelegramAPIError
    ):
        # a 5xx, a dropped connection, a garbled reply: worth another attempt
        return SendResult(outcome=SendOutcome.RETRY, error=text)
    return SendResult(outcome=SendOutcome.FAILED, error=text)


def _media_method(
    media_type: BroadcastMediaType,
    chat_id: int,
    file: Union[str, FSInputFile],
    caption: str,
    markup: Optional[InlineKeyboardMarkup],
) -> TelegramMethod[Message]:
    if media_type is BroadcastMediaType.PHOTO:
        return SendPhoto(
            chat_id=chat_id,
            photo=file,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    if media_type is BroadcastMediaType.VIDEO:
        return SendVideo(
            chat_id=chat_id,
            video=file,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    if media_type is BroadcastMediaType.ANIMATION:
        return SendAnimation(
            chat_id=chat_id,
            animation=file,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    return SendDocument(
        chat_id=chat_id,
        document=file,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


def _media_file_id(message: Message, media_type: BroadcastMediaType) -> Optional[str]:
    if media_type is BroadcastMediaType.PHOTO:
        return message.photo[-1].file_id if message.photo else None  # largest last
    if media_type is BroadcastMediaType.VIDEO:
        return message.video.file_id if message.video else None
    if media_type is BroadcastMediaType.ANIMATION:
        return message.animation.file_id if message.animation else None
    return message.document.file_id if message.document else None


async def send_broadcast_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]],
    media: Optional[OutgoingMedia],
) -> SendResult:
    markup = InlineKeyboardMarkup.model_validate(reply_markup) if reply_markup else None
    if media is not None and media.file_id is None and not (media.path and media.path.is_file()):
        # the caller skips the post; inside the send it would read as a network failure
        raise FileNotFoundError(media.path)
    try:
        if media is None:
            message = await bot.send_message(
                chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            return SendResult(outcome=SendOutcome.SENT, message_id=message.message_id)
        if media.file_id is not None:
            file: Union[str, FSInputFile] = media.file_id
        else:
            assert media.path is not None
            file = FSInputFile(media.path, filename=media.path.name)
        message = await bot(_media_method(media.media_type, chat_id, file, text, markup))
    except BOT_API_ERRORS as error:
        return _failure(error)
    return SendResult(
        outcome=SendOutcome.SENT,
        message_id=message.message_id,
        file_id=_media_file_id(message, media.media_type),
    )


async def get_bot_username(bot: Bot) -> Optional[str]:
    try:
        username = (await bot.get_me()).username
    except BOT_API_ERRORS as error:
        logger.info(f"getMe failed: {bot_api_error_text(error)}")
        return None
    return username or None


async def delete_telegram_message(bot: Bot, chat_id: int, message_id: int) -> SendResult:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BOT_API_ERRORS as error:
        logger.info(f"deleteMessage {chat_id}/{message_id} failed: {bot_api_error_text(error)}")
        return _failure(error)
    return SendResult(outcome=SendOutcome.SENT)
