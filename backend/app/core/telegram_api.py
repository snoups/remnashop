from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final, Optional

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import AiogramError, DetailedAiogramError
from aiogram.utils.token import TokenValidationError, validate_token
from python_socks import ProxyError

_DEFAULT_TIMEOUT_S: Final[float] = 10.0
# what a Bot API call outside the bot process can raise: the API's own answer,
# a network or decode failure (both aiogram's), a malformed token, a dead proxy
BOT_API_ERRORS: Final[tuple[type[Exception], ...]] = (
    AiogramError,
    TokenValidationError,
    ProxyError,
    OSError,
)


def bot_api_error_text(error: Exception) -> str:
    # Telegram's own description where there is one ("Unauthorized")
    if isinstance(error, DetailedAiogramError):
        return error.message
    return str(error) or type(error).__name__


def is_bot_token(token: str) -> bool:
    # aiogram refuses to build a Bot for a malformed token
    try:
        return validate_token(token)
    except TokenValidationError:
        return False


def bot_session(proxy: Optional[str], timeout: float) -> BaseSession:
    return AiohttpSession(proxy=proxy, timeout=timeout)


@asynccontextmanager
async def bot_client(
    token: str, proxy: Optional[str], *, timeout: float = _DEFAULT_TIMEOUT_S
) -> AsyncIterator[Bot]:
    """A Bot for calls made outside the telegram process; its HTTP session is
    closed on exit. Every caller passes the dashboard's bot proxy."""
    bot = Bot(token=token, session=bot_session(proxy, timeout))
    try:
        yield bot
    finally:
        await bot.session.close()
