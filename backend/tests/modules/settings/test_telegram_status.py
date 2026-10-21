from datetime import datetime, timezone

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.methods import GetMe
from aiogram.types import User, WebhookInfo

from app.modules.settings import telegram_status
from app.modules.settings.telegram_status import fetch_bot_status, fetch_bot_username
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot


async def test_a_refused_token_becomes_a_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = TelegramUnauthorizedError(method=GetMe(), message="Unauthorized")
    use_fake_bot(monkeypatch, FakeBotSession({"GetWebhookInfo": refused}))

    status = await fetch_bot_status("123:abc", None)

    assert status.is_configured is True
    assert status.error == "Unauthorized"


async def test_a_malformed_token_becomes_a_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_bot(monkeypatch, FakeBotSession())

    status = await fetch_bot_status("not-a-token", None)

    assert status.is_configured is True
    assert status.error


async def test_last_error_date_becomes_a_utc_datetime(monkeypatch: pytest.MonkeyPatch) -> None:
    info = WebhookInfo.model_validate(
        {
            "url": "https://x",
            "has_custom_certificate": False,
            "pending_update_count": 0,
            "last_error_message": "boom",
            "last_error_date": 1_700_000_000,
        }
    )
    session = use_fake_bot(monkeypatch, FakeBotSession({"GetWebhookInfo": info}))

    status = await fetch_bot_status("123:abc", "socks5://proxy:1080")

    assert status.last_error_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
    assert status.error == "boom"
    assert session.proxy == "socks5://proxy:1080"
    assert session.closed


@pytest.fixture(autouse=True)
def _clean_username_caches() -> None:
    telegram_status._USERNAME_CACHE.clear()
    telegram_status._USERNAME_FAILED_UNTIL.clear()


async def test_a_failed_username_lookup_is_not_retried_inside_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    session = use_fake_bot(
        monkeypatch, FakeBotSession({"GetMe": TelegramNetworkError(method=GetMe(), message="down")})
    )
    monkeypatch.setattr(telegram_status.time, "monotonic", lambda: now)

    assert await fetch_bot_username("123:abc", None) is None
    assert await fetch_bot_username("123:abc", None) is None
    assert len(session.called("GetMe")) == 1

    now += 61
    assert await fetch_bot_username("123:abc", None) is None
    assert len(session.called("GetMe")) == 2


async def test_the_username_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    me = User(id=123, is_bot=True, first_name="bot", username="shop_bot")
    session = use_fake_bot(monkeypatch, FakeBotSession({"GetMe": me}))

    assert await fetch_bot_username("123:abc", None) == "shop_bot"
    assert await fetch_bot_username("123:abc", None) == "shop_bot"
    assert len(session.called("GetMe")) == 1
