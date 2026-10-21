import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message

from app.modules.notifications import telegram
from app.modules.notifications.telegram import (
    TelegramSendResult,
    send_telegram_message,
    send_telegram_text,
)
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot

_TOKEN = "123:abc"


def _message(method: SendMessage) -> Message:
    return Message.model_validate(
        {"message_id": 1, "date": 0, "chat": Chat(id=int(method.chat_id), type="private")}
    )


def _flood(seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=1, text="hi"), message="Too Many Requests", retry_after=seconds
    )


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
    replies: list[object] = [_flood(3), None]

    def _send(method: SendMessage) -> object:
        reply = replies.pop(0)
        return reply if reply is not None else _message(method)

    use_fake_bot(monkeypatch, FakeBotSession({"SendMessage": _send}))

    assert await send_telegram_message(_TOKEN, None, 1, "hi") is True
    assert slept == [3]


async def test_second_rate_limit_gives_up(
    monkeypatch: pytest.MonkeyPatch, slept: list[float]
) -> None:
    use_fake_bot(monkeypatch, FakeBotSession({"SendMessage": _flood(1)}))

    assert await send_telegram_message(_TOKEN, None, 1, "hi") is False


async def test_a_long_flood_wait_is_not_waited_out(
    monkeypatch: pytest.MonkeyPatch, slept: list[float]
) -> None:
    use_fake_bot(monkeypatch, FakeBotSession({"SendMessage": _flood(600)}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FAILED
    assert slept == []


async def test_blocked_bot_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = TelegramForbiddenError(
        method=SendMessage(chat_id=1, text="hi"), message="Forbidden: bot was blocked by the user"
    )
    use_fake_bot(monkeypatch, FakeBotSession({"SendMessage": blocked}))

    assert await send_telegram_text(_TOKEN, None, 1, "hi") is TelegramSendResult.FORBIDDEN
    assert await send_telegram_message(_TOKEN, None, 1, "hi") is False


async def test_a_malformed_token_fails_instead_of_raising() -> None:
    assert await send_telegram_text("not-a-token", None, 1, "hi") is TelegramSendResult.FAILED
