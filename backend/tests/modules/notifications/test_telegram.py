from typing import Any

import pytest

from app.modules.notifications import telegram
from app.modules.notifications.telegram import (
    TelegramSendResult,
    send_telegram_message,
    send_telegram_text,
)
from tests.fakes.telegram_bot import FakeBotSession, flood, refusal, use_fake_bot

_TOKEN = "123:abc"


@pytest.fixture
def slept(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []

    async def _sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(telegram.asyncio, "sleep", _sleep)
    return calls


async def test_rate_limited_send_waits_and_retries_once(
    monkeypatch: pytest.MonkeyPatch, slept: list[float]
) -> None:
    replies: list[object] = [flood(3), None]

    def _send(params: dict[str, Any]) -> object:
        reply = replies.pop(0)
        return reply if reply is not None else {"message_id": 1}

    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": _send}))

    assert await send_telegram_message(_TOKEN, None, 1, "hi") is True
    assert slept == [3]


async def test_second_rate_limit_gives_up(
    monkeypatch: pytest.MonkeyPatch, slept: list[float]
) -> None:
    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": flood(1)}))

    assert await send_telegram_message(_TOKEN, None, 1, "hi") is False


async def test_a_long_flood_wait_is_not_waited_out(
    monkeypatch: pytest.MonkeyPatch, slept: list[float]
) -> None:
    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": flood(600)}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FAILED
    assert slept == []


async def test_blocked_bot_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = refusal(403, "Forbidden: bot was blocked by the user")
    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": blocked}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FORBIDDEN
    assert await send_telegram_message(_TOKEN, None, 1, "hi") is False


async def test_a_chat_telegram_does_not_know_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    unknown = refusal(400, "Bad Request: chat not found")
    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": unknown}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FORBIDDEN


async def test_any_other_bad_request_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    malformed = refusal(400, "Bad Request: can't parse entities")
    use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": malformed}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FAILED


async def test_a_malformed_token_fails_instead_of_raising() -> None:
    assert await send_telegram_text("not-a-token", None, 1, "hi") is TelegramSendResult.FAILED
