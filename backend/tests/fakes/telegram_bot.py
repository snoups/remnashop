from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional, Union

import pytest

from app.core import telegram_api
from app.core.telegram_api import BotApiRefusedError, BotSession

# a reply: the result itself, an exception to raise, or a callable of the call's params
Reply = Union[object, BaseException, Callable[[dict[str, Any]], object]]


def refusal(
    code: int, description: str, *, method: str = "", retry_after: Optional[float] = None
) -> BotApiRefusedError:
    return BotApiRefusedError(method, code, description, retry_after)


def flood(seconds: float) -> BotApiRefusedError:
    return refusal(HTTPStatus.TOO_MANY_REQUESTS, "Too Many Requests", retry_after=seconds)


class FakeBotSession(BotSession):
    """Answers Bot API calls by method name (`getMe`, `sendMessage`) and records
    each call's params; an upload's file lands in its params as a Path."""

    def __init__(
        self,
        replies: Optional[dict[str, Reply]] = None,
        files: Optional[dict[str, bytes]] = None,
    ) -> None:
        super().__init__(None, 0)
        self.replies: dict[str, Reply] = dict(replies or {})
        self.files: dict[str, bytes] = dict(files or {})
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def called(self, method: str) -> list[dict[str, Any]]:
        return [params for name, params in self.calls if name == method]

    async def request(
        self,
        token: str,
        method: str,
        params: dict[str, Any],
        upload: Optional[tuple[str, Path]] = None,
    ) -> Any:
        if upload is not None:
            params = {**params, upload[0]: upload[1]}
        self.calls.append((method, params))
        if method not in self.replies:
            raise AssertionError(f"unexpected Bot API call {method}")
        reply = self.replies[method]
        if isinstance(reply, BaseException):
            raise reply
        if callable(reply):
            reply = reply(params)
            if isinstance(reply, BaseException):
                raise reply
        return reply

    async def fetch(self, token: str, file_path: str) -> bytes:
        if file_path in self.files:
            return self.files[file_path]
        raise AssertionError(f"unexpected download {file_path}")

    async def close(self) -> None:
        self.closed = True


def use_fake_bot(monkeypatch: pytest.MonkeyPatch, session: FakeBotSession) -> FakeBotSession:
    def _session(proxy: Optional[str], timeout: float) -> BotSession:
        session.proxy = proxy
        session.timeout = timeout
        return session

    monkeypatch.setattr(telegram_api, "bot_session", _session)
    return session
