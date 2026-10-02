from typing import Any, Final, Optional

import httpx

from app.modules.settings.dto import BotStatusDto

TELEGRAM_API_URL: Final[str] = "https://api.telegram.org"
_TIMEOUT_SECONDS: Final[float] = 5.0
# token -> username; a bot's username can't change without a new token
_USERNAME_CACHE: Final[dict[str, str]] = {}


async def fetch_bot_status(token: str, proxy: Optional[str]) -> BotStatusDto:
    # getWebhookInfo is the one call that answers "is the bot actually up": it
    # needs a valid token, and its `url` stays empty until the telegram process
    # has started and registered the webhook.
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.get(f"{TELEGRAM_API_URL}/bot{token}/getWebhookInfo")
    except httpx.HTTPError as error:
        return BotStatusDto(is_configured=True, error=str(error) or type(error).__name__)

    payload: dict[str, Any] = response.json()
    if not payload.get("ok"):
        return BotStatusDto(is_configured=True, error=payload.get("description", "Unknown error"))

    info: dict[str, Any] = payload["result"]
    return BotStatusDto(
        is_configured=True,
        webhook_url=info.get("url") or None,
        pending_update_count=info.get("pending_update_count", 0),
        error=info.get("last_error_message"),
    )


async def fetch_bot_username(token: str, proxy: Optional[str]) -> Optional[str]:
    if token in _USERNAME_CACHE:
        return _USERNAME_CACHE[token]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.get(f"{TELEGRAM_API_URL}/bot{token}/getMe")
        payload: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not payload.get("ok"):
        return None
    username: str = payload["result"]["username"]
    _USERNAME_CACHE[token] = username
    return username
