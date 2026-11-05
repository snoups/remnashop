import pytest

from app.core.telegram_api import (
    BotApiError,
    BotApiRefusedError,
    bot_client,
    is_bot_token,
    unwrap_reply,
)
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot


def test_is_bot_token() -> None:
    assert is_bot_token("123:abc") is True
    assert is_bot_token("not-a-token") is False
    assert is_bot_token("abc:def") is False
    assert is_bot_token("123:") is False
    assert is_bot_token("123:ab c") is False


async def test_bot_client_closes_its_session_and_uses_the_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession())

    async with bot_client("123:abc", "socks5://proxy:1080") as bot:
        assert (bot.token, bot.id) == ("123:abc", 123)

    assert session.proxy == "socks5://proxy:1080"
    assert session.closed


async def test_a_malformed_token_never_opens_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession())

    with pytest.raises(BotApiError):
        async with bot_client("not-a-token", None):
            pass

    assert session.calls == []


async def test_none_params_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"sendMessage": {"message_id": 1}}))

    async with bot_client("123:abc", None) as bot:
        await bot.call("sendMessage", chat_id=1, text="hi", reply_markup=None)

    assert session.called("sendMessage") == [{"chat_id": 1, "text": "hi"}]


async def test_download_resolves_the_file_path(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_bot(
        monkeypatch,
        FakeBotSession({"getFile": {"file_path": "stickers/a.webp"}}, {"stickers/a.webp": b"x"}),
    )

    async with bot_client("123:abc", None) as bot:
        assert await bot.download("f1") == b"x"


def test_unwrap_reply_returns_the_result() -> None:
    assert unwrap_reply("getMe", {"ok": True, "result": {"id": 1}}, 200) == {"id": 1}


def test_unwrap_reply_raises_a_refusal_with_retry_after() -> None:
    with pytest.raises(BotApiRefusedError) as raised:
        unwrap_reply(
            "sendMessage",
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 5",
                "parameters": {"retry_after": 5},
            },
            429,
        )

    assert (raised.value.error_code, raised.value.retry_after) == (429, 5.0)
    assert str(raised.value) == "Too Many Requests: retry after 5"


@pytest.mark.parametrize("payload", [None, [], {"result": 1}, "<html>"])
def test_unwrap_reply_rejects_a_garbled_reply(payload: object) -> None:
    with pytest.raises(BotApiError) as raised:
        unwrap_reply("getMe", payload, 200)

    assert not isinstance(raised.value, BotApiRefusedError)


def test_unwrap_reply_falls_back_to_the_http_status() -> None:
    with pytest.raises(BotApiRefusedError) as raised:
        unwrap_reply("sendMessage", {"ok": False, "parameters": {"retry_after": "soon"}}, 502)

    assert (raised.value.error_code, raised.value.retry_after) == (502, None)
