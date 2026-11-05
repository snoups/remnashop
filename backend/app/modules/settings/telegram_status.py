import time
from datetime import datetime, timezone
from typing import Final, Optional

from app.core.telegram_api import BOT_API_ERRORS, bot_api_error_text, bot_client
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
        async with bot_client(token, proxy, timeout=_TIMEOUT_SECONDS) as bot:
            info = await bot.call("getWebhookInfo")
    except BOT_API_ERRORS as error:
        return BotStatusDto(is_configured=True, error=bot_api_error_text(error))
    return BotStatusDto(
        is_configured=True,
        webhook_url=info.get("url") or None,
        pending_update_count=info.get("pending_update_count", 0),
        error=info.get("last_error_message"),
        last_error_at=_unix_time(info.get("last_error_date")),
    )


async def fetch_bot_username(token: str, proxy: Optional[str]) -> Optional[str]:
    if token in _USERNAME_CACHE:
        return _USERNAME_CACHE[token]
    if _USERNAME_FAILED_UNTIL.get(token, 0.0) > time.monotonic():
        return None
    username: Optional[str] = None
    try:
        async with bot_client(token, proxy, timeout=_TIMEOUT_SECONDS) as bot:
            found = (await bot.call("getMe")).get("username")
            username = found if isinstance(found, str) and found else None
    except BOT_API_ERRORS:
        pass
    if username is None:
        _USERNAME_FAILED_UNTIL[token] = time.monotonic() + _FAILURE_TTL_SECONDS
        return None
    _USERNAME_CACHE[token] = username
    return username


async def is_bot_channel_admin(token: str, proxy: Optional[str], channel_id: int) -> bool:
    try:
        async with bot_client(token, proxy, timeout=_TIMEOUT_SECONDS) as bot:
            member = await bot.call("getChatMember", chat_id=channel_id, user_id=bot.id)
    except BOT_API_ERRORS:
        return False
    return member.get("status") in _CHANNEL_ADMIN_STATUSES


def _unix_time(value: Optional[int]) -> Optional[datetime]:
    return datetime.fromtimestamp(value, timezone.utc) if value is not None else None
