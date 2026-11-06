from collections.abc import AsyncGenerator, Callable
from typing import Any, Optional, Union

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod

# a reply: the result itself, an exception to raise, or a callable of the method
Reply = Union[object, BaseException, Callable[[TelegramMethod[Any]], object]]


class FakeAiogramSession(BaseSession):
    """An aiogram session for the bot process's handlers: answers Bot API calls
    by method class name (`GetMe`, `SendMessage`) and records them."""

    def __init__(
        self,
        replies: Optional[dict[str, Reply]] = None,
        files: Optional[dict[str, bytes]] = None,
    ) -> None:
        super().__init__()
        self.replies: dict[str, Reply] = dict(replies or {})
        self.files: dict[str, bytes] = dict(files or {})
        self.calls: list[TelegramMethod[Any]] = []
        self.proxy: Optional[str] = None
        self.closed = False

    def called(self, name: str) -> list[TelegramMethod[Any]]:
        return [call for call in self.calls if type(call).__name__ == name]

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: Optional[int] = None
    ) -> Any:
        self.calls.append(method)
        name = type(method).__name__
        if name not in self.replies:
            raise AssertionError(f"unexpected Bot API call {name}")
        reply = self.replies[name]
        if isinstance(reply, BaseException):
            raise reply
        if callable(reply):
            result = reply(method)
            if isinstance(result, BaseException):
                raise result
            return result
        return reply

    async def stream_content(
        self,
        url: str,
        headers: Optional[dict[str, Any]] = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        for path, content in self.files.items():
            if url.endswith(path):
                yield content
                return
        raise AssertionError(f"unexpected download {url}")

    async def close(self) -> None:
        self.closed = True
