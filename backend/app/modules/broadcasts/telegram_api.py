from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import auto
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final, Optional

from loguru import logger

from app.core.enums import BroadcastMediaType, UpperStrEnum
from app.core.telegram_api import (
    BOT_API_ERRORS,
    BotApi,
    BotApiRefusedError,
    bot_api_error_text,
    bot_client,
)
from app.modules.broadcasts.mp4 import video_meta

_TIMEOUT_SECONDS: Final[float] = 30.0
_HTML: Final[str] = "HTML"
# media type -> (Bot API method, its file field)
_MEDIA_METHODS: Final[dict[BroadcastMediaType, tuple[str, str]]] = {
    BroadcastMediaType.PHOTO: ("sendPhoto", "photo"),
    BroadcastMediaType.VIDEO: ("sendVideo", "video"),
    BroadcastMediaType.ANIMATION: ("sendAnimation", "animation"),
    BroadcastMediaType.DOCUMENT: ("sendDocument", "document"),
}


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
    def open(self, token: str, proxy: Optional[str]) -> AbstractAsyncContextManager[BotApi]:
        return bot_client(token, proxy, timeout=_TIMEOUT_SECONDS)


def _failure(error: Exception) -> SendResult:
    text = bot_api_error_text(error)
    if not isinstance(error, BotApiRefusedError):
        # a dropped connection, a garbled reply: worth another attempt
        return SendResult(outcome=SendOutcome.RETRY, error=text)
    if error.error_code == HTTPStatus.TOO_MANY_REQUESTS:
        return SendResult(outcome=SendOutcome.RETRY, error=text, retry_after=error.retry_after)
    if error.error_code == HTTPStatus.UNAUTHORIZED:
        return SendResult(outcome=SendOutcome.UNAUTHORIZED, error=text)
    if error.error_code == HTTPStatus.FORBIDDEN:
        return SendResult(outcome=SendOutcome.BLOCKED, error=text)
    if error.error_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return SendResult(outcome=SendOutcome.RETRY, error=text)
    return SendResult(outcome=SendOutcome.FAILED, error=text)


def _media_file_id(message: dict[str, Any], media_type: BroadcastMediaType) -> Optional[str]:
    _, field = _MEDIA_METHODS[media_type]
    media = message.get(field)
    if media_type is BroadcastMediaType.PHOTO:
        return media[-1]["file_id"] if media else None  # largest last
    return media.get("file_id") if media else None


def _video_params(path: Path) -> dict[str, Any]:
    # without them Telegram shows the video as a square until a client downloads it
    meta = video_meta(path)
    if meta is None:
        return {}
    return {"width": meta.width, "height": meta.height, "duration": meta.duration}


async def send_broadcast_message(
    bot: BotApi,
    chat_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]],
    media: Optional[OutgoingMedia],
) -> SendResult:
    if media is not None and media.file_id is None and not (media.path and media.path.is_file()):
        # the caller skips the post; inside the send it would read as a network failure
        raise FileNotFoundError(media.path)
    try:
        if media is None:
            message = await bot.call(
                "sendMessage",
                chat_id=chat_id,
                text=text,
                parse_mode=_HTML,
                reply_markup=reply_markup,
            )
            return SendResult(outcome=SendOutcome.SENT, message_id=message["message_id"])
        method, field = _MEDIA_METHODS[media.media_type]
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "caption": text,
            "parse_mode": _HTML,
            "reply_markup": reply_markup,
        }
        if media.file_id is not None:
            message = await bot.call(method, **params, **{field: media.file_id})
        else:
            assert media.path is not None
            if media.media_type is BroadcastMediaType.VIDEO:
                params |= _video_params(media.path)
            message = await bot.upload(method, field, media.path, **params)
    except BOT_API_ERRORS as error:
        return _failure(error)
    return SendResult(
        outcome=SendOutcome.SENT,
        message_id=message["message_id"],
        file_id=_media_file_id(message, media.media_type),
    )


async def get_bot_username(bot: BotApi) -> Optional[str]:
    try:
        username = (await bot.call("getMe")).get("username")
    except BOT_API_ERRORS as error:
        logger.info(f"getMe failed: {bot_api_error_text(error)}")
        return None
    return username if isinstance(username, str) and username else None


async def delete_telegram_message(bot: BotApi, chat_id: int, message_id: int) -> SendResult:
    try:
        await bot.call("deleteMessage", chat_id=chat_id, message_id=message_id)
    except BOT_API_ERRORS as error:
        logger.info(f"deleteMessage {chat_id}/{message_id} failed: {bot_api_error_text(error)}")
        return _failure(error)
    return SendResult(outcome=SendOutcome.SENT)
