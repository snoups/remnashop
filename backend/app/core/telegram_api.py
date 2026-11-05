import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Final, Optional

import aiohttp
from aiohttp_socks import ProxyConnector
from python_socks import ProxyError

_API_URL: Final[str] = "https://api.telegram.org"
_DEFAULT_TIMEOUT_S: Final[float] = 10.0


class BotApiError(Exception):
    """A Bot API call that got no usable answer: a malformed token, a network
    failure, a garbled reply. The message never carries the request URL (it
    holds the token)."""


class BotApiRefusedError(BotApiError):
    """Telegram answered `ok: false`."""

    def __init__(
        self, method: str, error_code: int, description: str, retry_after: Optional[float]
    ) -> None:
        super().__init__(description)
        self.method = method
        self.error_code = error_code
        self.description = description
        self.retry_after = retry_after


# what a Bot API call can raise: BotApiError (a refusal included), a dead proxy
BOT_API_ERRORS: Final[tuple[type[Exception], ...]] = (BotApiError, ProxyError, OSError)


def bot_api_error_text(error: Exception) -> str:
    return str(error) or type(error).__name__


def is_bot_token(token: str) -> bool:
    if any(char.isspace() for char in token):
        return False
    bot_id, sep, secret = token.partition(":")
    return bool(sep) and bot_id.isdigit() and bool(secret)


def unwrap_reply(method: str, payload: Any, status: int) -> Any:
    if not isinstance(payload, dict) or "ok" not in payload:
        raise BotApiError(f"{method}: unexpected reply")
    if payload["ok"]:
        return payload.get("result")
    error_code = payload.get("error_code")
    raise BotApiRefusedError(
        method,
        error_code if isinstance(error_code, int) else status,
        str(payload.get("description") or ""),
        _retry_after(payload.get("parameters")),
    )


def _retry_after(parameters: Any) -> Optional[float]:
    # an unreadable flood wait is an ordinary refusal
    value = parameters.get("retry_after") if isinstance(parameters, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def _form_value(value: Any) -> str:
    # multipart fields are strings; nested objects (reply_markup) go as JSON
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class BotSession:
    def __init__(self, proxy: Optional[str], timeout: float) -> None:
        self.proxy = proxy
        self.timeout = timeout
        self._http: Optional[aiohttp.ClientSession] = None

    def _client(self) -> aiohttp.ClientSession:
        if self._http is None:
            self._http = aiohttp.ClientSession(
                connector=ProxyConnector.from_url(self.proxy) if self.proxy else None,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._http

    async def request(
        self,
        token: str,
        method: str,
        params: dict[str, Any],
        upload: Optional[tuple[str, Path]] = None,
    ) -> Any:
        url = f"{_API_URL}/bot{token}/{method}"
        try:
            if upload is None:
                async with self._client().post(url, json=params) as response:
                    status = response.status
                    payload = await response.json(content_type=None)
            else:
                field, path = upload
                with path.open("rb") as file:
                    form = aiohttp.FormData()
                    for name, value in params.items():
                        form.add_field(name, _form_value(value))
                    form.add_field(field, file, filename=path.name)
                    async with self._client().post(url, data=form) as response:
                        status = response.status
                        payload = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            # from None, and no str(error): aiohttp's message can carry the URL
            raise BotApiError(f"{method}: {type(error).__name__}") from None
        return unwrap_reply(method, payload, status)

    async def fetch(self, token: str, file_path: str) -> bytes:
        url = f"{_API_URL}/file/bot{token}/{file_path}"
        try:
            async with self._client().get(url) as response:
                response.raise_for_status()
                return await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            raise BotApiError(f"download: {type(error).__name__}") from None

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()


class BotApi:
    def __init__(self, token: str, session: BotSession) -> None:
        self.token = token
        self.id = int(token.partition(":")[0])
        self.session = session

    async def call(self, method: str, **params: Any) -> Any:
        return await self.session.request(self.token, method, _present(params))

    async def upload(self, method: str, field: str, path: Path, **params: Any) -> Any:
        return await self.session.request(self.token, method, _present(params), (field, path))

    async def download(self, file_id: str) -> bytes:
        file = await self.call("getFile", file_id=file_id)
        file_path = file.get("file_path") if isinstance(file, dict) else None
        if not file_path:
            raise BotApiError("getFile: no file_path")
        return await self.session.fetch(self.token, file_path)


def _present(params: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in params.items() if value is not None}


def bot_session(proxy: Optional[str], timeout: float) -> BotSession:
    return BotSession(proxy, timeout)


@asynccontextmanager
async def bot_client(
    token: str, proxy: Optional[str], *, timeout: float = _DEFAULT_TIMEOUT_S
) -> AsyncIterator[BotApi]:
    """A Bot API client; its HTTP session is closed on exit. Every caller
    passes the dashboard's bot proxy."""
    if not is_bot_token(token):
        raise BotApiError("Malformed bot token")
    session = bot_session(proxy, timeout)
    try:
        yield BotApi(token, session)
    finally:
        await session.close()
