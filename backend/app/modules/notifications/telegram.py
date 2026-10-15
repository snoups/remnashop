import asyncio
from enum import auto
from typing import Any, Final, Optional

import httpx
from loguru import logger

from app.core.enums import UpperStrEnum
from app.core.telegram_api import bot_method_url, retry_after_seconds

# an alert waits out a short flood-wait once; a long one fails the delivery
_MAX_RETRY_AFTER_S: Final[float] = 30.0
TELEGRAM_TIMEOUT_SECONDS: Final[float] = 10.0
_RATE_LIMITED: Final[int] = 429
_FORBIDDEN: Final[int] = 403


class TelegramSendResult(UpperStrEnum):
    SENT = auto()
    # never pressed /start or blocked the bot: retrying won't help
    FORBIDDEN = auto()
    FAILED = auto()


async def _post(client: httpx.AsyncClient, token: str, chat_id: int, text: str) -> dict[str, Any]:
    response = await client.post(
        bot_method_url(token, "sendMessage"),
        json={"chat_id": chat_id, "text": text},
    )
    payload: dict[str, Any] = response.json()
    return payload


async def _post_with_retry(
    client: httpx.AsyncClient, token: str, chat_id: int, text: str
) -> dict[str, Any]:
    payload = await _post(client, token, chat_id, text)
    if payload.get("error_code") == _RATE_LIMITED:
        retry_after = retry_after_seconds(payload)
        if retry_after > _MAX_RETRY_AFTER_S:
            return payload
        await asyncio.sleep(retry_after)
        payload = await _post(client, token, chat_id, text)
    return payload


async def send_telegram_text(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> TelegramSendResult:
    # plain text: logins and error messages in the payload are user-controlled
    try:
        if client is None:
            async with httpx.AsyncClient(
                timeout=TELEGRAM_TIMEOUT_SECONDS, proxy=proxy
            ) as own_client:
                payload = await _post_with_retry(own_client, token, chat_id, text)
        else:
            payload = await _post_with_retry(client, token, chat_id, text)
    except (httpx.HTTPError, ValueError) as error:
        logger.warning(f"Telegram notification to {chat_id} failed: {type(error).__name__}")
        return TelegramSendResult.FAILED
    if not payload.get("ok"):
        logger.info(f"Telegram notification to {chat_id} refused: {payload.get('description')}")
        if payload.get("error_code") == _FORBIDDEN:
            return TelegramSendResult.FORBIDDEN
        return TelegramSendResult.FAILED
    return TelegramSendResult.SENT


async def send_telegram_message(
    token: str,
    proxy: Optional[str],
    chat_id: int,
    text: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    result = await send_telegram_text(token, proxy, chat_id, text, client=client)
    return result is TelegramSendResult.SENT
