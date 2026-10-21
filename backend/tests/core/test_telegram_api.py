import pytest

from app.core.telegram_api import bot_client, is_bot_token
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot


def test_is_bot_token() -> None:
    assert is_bot_token("123:abc") is True
    assert is_bot_token("not-a-token") is False


async def test_bot_client_closes_its_session_and_uses_the_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession())

    async with bot_client("123:abc", "socks5://proxy:1080") as bot:
        assert bot.token == "123:abc"

    assert session.proxy == "socks5://proxy:1080"
    assert session.closed
