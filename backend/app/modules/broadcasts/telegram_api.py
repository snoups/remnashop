import json
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Any, Final, Optional

import httpx
from loguru import logger

from app.core.enums import BroadcastMediaType, UpperStrEnum
from app.core.telegram_api import bot_method_url, retry_after_seconds

_TIMEOUT_SECONDS: Final[float] = 30.0
_METHOD_BY_MEDIA: Final[dict[BroadcastMediaType, tuple[str, str]]] = {
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
    def open(self, proxy: Optional[str]) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy)


def _file_id(result: dict[str, Any], field: str) -> Optional[str]:
    value = result.get(field)
    if isinstance(value, list) and value:
        value = value[-1]  # photo sizes: largest last
    return value.get("file_id") if isinstance(value, dict) else None


def _result(status_code: int, payload: dict[str, Any], field: str) -> SendResult:
    if payload.get("ok"):
        result = payload.get("result")
        if not isinstance(result, dict):
            result = {}
        return SendResult(
            outcome=SendOutcome.SENT,
            message_id=result.get("message_id"),
            file_id=_file_id(result, field) if field else None,
        )
    description = str(payload.get("description") or status_code)
    if status_code == 429:
        return SendResult(
            outcome=SendOutcome.RETRY, error=description, retry_after=retry_after_seconds(payload)
        )
    if status_code == 401:
        return SendResult(outcome=SendOutcome.UNAUTHORIZED, error=description)
    if status_code == 403:
        return SendResult(outcome=SendOutcome.BLOCKED, error=description)
    if status_code >= 500:
        return SendResult(outcome=SendOutcome.RETRY, error=description)
    return SendResult(outcome=SendOutcome.FAILED, error=description)


async def send_broadcast_message(
    client: httpx.AsyncClient,
    token: str,
    chat_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]],
    media: Optional[OutgoingMedia],
) -> SendResult:
    fields: dict[str, Any] = {"chat_id": chat_id, "parse_mode": "HTML"}
    if reply_markup is not None:
        fields["reply_markup"] = reply_markup
    method, field = ("sendMessage", "") if media is None else _METHOD_BY_MEDIA[media.media_type]
    url = bot_method_url(token, method)
    try:
        if media is None:
            response = await client.post(url, json={**fields, "text": text})
        elif media.file_id is not None:
            response = await client.post(
                url, json={**fields, "caption": text, field: media.file_id}
            )
        else:
            assert media.path is not None
            form = {k: json.dumps(v) if isinstance(v, dict) else str(v) for k, v in fields.items()}
            form["caption"] = text
            with media.path.open("rb") as handle:
                response = await client.post(
                    url, data=form, files={field: (media.path.name, handle, media.content_type)}
                )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return SendResult(outcome=SendOutcome.RETRY, error=type(error).__name__)
    if not isinstance(payload, dict):
        return SendResult(outcome=SendOutcome.RETRY, error="Unexpected response")
    return _result(response.status_code, payload, field)


async def get_bot_username(client: httpx.AsyncClient, token: str) -> Optional[str]:
    try:
        payload = (await client.post(bot_method_url(token, "getMe"))).json()
    except (httpx.HTTPError, ValueError) as error:
        logger.info(f"getMe failed: {type(error).__name__}")
        return None
    result = payload.get("result") if isinstance(payload, dict) else None
    username = result.get("username") if isinstance(result, dict) else None
    return username if isinstance(username, str) and username else None


async def delete_telegram_message(
    client: httpx.AsyncClient, token: str, chat_id: int, message_id: int
) -> SendResult:
    try:
        response = await client.post(
            bot_method_url(token, "deleteMessage"),
            json={"chat_id": chat_id, "message_id": message_id},
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.info(f"deleteMessage {chat_id}/{message_id} failed: {type(error).__name__}")
        return SendResult(outcome=SendOutcome.RETRY, error=type(error).__name__)
    if not isinstance(payload, dict):
        return SendResult(outcome=SendOutcome.RETRY, error="Unexpected response")
    return _result(response.status_code, payload, "")
