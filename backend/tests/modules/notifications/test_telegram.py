import httpx
import pytest

from app.modules.notifications import telegram
from app.modules.notifications.telegram import (
    TelegramSendResult,
    send_telegram_message,
    send_telegram_text,
)


async def test_rate_limited_send_waits_and_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = [
        httpx.Response(
            429, json={"ok": False, "error_code": 429, "parameters": {"retry_after": 3}}
        ),
        httpx.Response(200, json={"ok": True, "result": {}}),
    ]
    slept: list[float] = []

    async def _post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return replies.pop(0)

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    monkeypatch.setattr(telegram.asyncio, "sleep", _sleep)

    assert await send_telegram_message("t", None, 1, "hi") is True
    assert slept == [3]


async def test_second_rate_limit_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            429, json={"ok": False, "error_code": 429, "parameters": {"retry_after": 1}}
        )

    async def _sleep(seconds: float) -> None: ...

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    monkeypatch.setattr(telegram.asyncio, "sleep", _sleep)

    assert await send_telegram_message("t", None, 1, "hi") is False


async def test_blocked_bot_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot was blocked by the user",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    assert await send_telegram_text("t", None, 1, "hi") is TelegramSendResult.FORBIDDEN
    assert await send_telegram_message("t", None, 1, "hi") is False
