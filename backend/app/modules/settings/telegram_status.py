import time
from datetime import datetime, timezone
from typing import Any, Final, Optional

import httpx

from app.core.telegram_api import bot_method_url
from app.modules.settings.dto import BotStatusDto

_TIMEOUT_SECONDS: Final[float] = 5.0
# token -> username; a bot's username can't change without a new token
_USERNAME_CACHE: Final[dict[str, str]] = {}
# token -> monotonic deadline; while Telegram is down every public-settings call
# would otherwise wait out the full timeout
_USERNAME_FAILED_UNTIL: Final[dict[str, float]] = {}
_FAILURE_TTL_SECONDS: Final[float] = 60.0
_CHANNEL_ADMIN_STATUSES: Final[frozenset[str]] = frozenset({"administrator", "creator"})


async def fetch_bot_status(token: str, proxy: Optional[str]) -> BotStatusDto:
    # getWebhookInfo is the one call that answers "is the bot actually up": it
    # needs a valid token, and its `url` stays empty until the telegram process
    # has started and registered the webhook.
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.get(bot_method_url(token, "getWebhookInfo"))
        payload: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return BotStatusDto(is_configured=True, error=str(error) or type(error).__name__)

    if not payload.get("ok"):
        return BotStatusDto(is_configured=True, error=payload.get("description", "Unknown error"))

    info: dict[str, Any] = payload["result"]
    last_error_date = info.get("last_error_date")
    return BotStatusDto(
        is_configured=True,
        webhook_url=info.get("url") or None,
        pending_update_count=info.get("pending_update_count", 0),
        error=info.get("last_error_message"),
        last_error_at=(
            datetime.fromtimestamp(last_error_date, tz=timezone.utc) if last_error_date else None
        ),
    )


async def fetch_bot_username(token: str, proxy: Optional[str]) -> Optional[str]:
    if token in _USERNAME_CACHE:
        return _USERNAME_CACHE[token]
    if _USERNAME_FAILED_UNTIL.get(token, 0.0) > time.monotonic():
        return None
    username: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.get(bot_method_url(token, "getMe"))
        payload: dict[str, Any] = response.json()
        if payload.get("ok"):
            username = payload.get("result", {}).get("username")
    except (httpx.HTTPError, ValueError):
        pass
    if username is None:
        _USERNAME_FAILED_UNTIL[token] = time.monotonic() + _FAILURE_TTL_SECONDS
        return None
    _USERNAME_CACHE[token] = username
    return username


async def is_bot_channel_admin(token: str, proxy: Optional[str], channel_id: int) -> bool:
    try:
        bot_id = int(token.split(":", 1)[0])
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.get(
                bot_method_url(token, "getChatMember"),
                params={"chat_id": channel_id, "user_id": bot_id},
            )
        payload: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    if not payload.get("ok"):
        return False
    return payload.get("result", {}).get("status") in _CHANNEL_ADMIN_STATUSES
