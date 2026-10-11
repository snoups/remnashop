from types import SimpleNamespace
from typing import Any, Optional

from redis.asyncio import Redis

from app.core.enums import Locale
from app.modules.cabinet_auth import ConfirmDeeplinkUseCase, DeeplinkStore, InviteCodesDto
from app.telegram.routers.cabinet_auth.handlers import on_confirm_webauth, on_start_webauth


class _Runner:
    def get(self, key: str, **kwargs: Any) -> str:
        return key


class _Hub:
    def get_translator_by_locale(self, locale: str) -> _Runner:
        return _Runner()


class _Message:
    def __init__(self, text: str) -> None:
        self.text = text
        self.sent: list[dict[str, Any]] = []

    async def answer(self, text: str, reply_markup: Optional[Any] = None) -> None:
        self.sent.append({"text": text, "markup": reply_markup})


_USER: Any = SimpleNamespace(language=Locale.EN)


async def test_start_only_asks_and_never_confirms(redis: Redis) -> None:
    store = DeeplinkStore(redis)
    token, _ = await store.create(InviteCodesDto(), "203.0.113.1", "Firefox")
    message = _Message(f"/start webauth_{token}")

    await on_start_webauth(message, store, _Hub(), _USER)  # type: ignore[arg-type]

    assert message.sent[0]["text"] == "ntf-cabinet-login-ask"
    assert message.sent[0]["markup"].inline_keyboard[0][0].callback_data == f"webauth:{token}"
    assert len(message.sent[0]["markup"].inline_keyboard[0][0].callback_data.encode()) <= 64
    assert await store.peek(token) is not None


async def test_start_with_unknown_token_says_expired(redis: Redis) -> None:
    message = _Message("/start webauth_" + "x" * 43)

    await on_start_webauth(message, DeeplinkStore(redis), _Hub(), _USER)  # type: ignore[arg-type]

    assert message.sent[0]["text"] == "ntf-cabinet-login.expired"


async def test_callback_confirms_and_edits_the_message(redis: Redis) -> None:
    store = DeeplinkStore(redis)
    token, _ = await store.create(InviteCodesDto(), "203.0.113.1", "Firefox")
    callback: Any = SimpleNamespace(
        data=f"webauth:{token}",
        from_user=SimpleNamespace(id=9, full_name="Ann", username=None, language_code="en"),
        message=None,
        answer=lambda: _noop(),
    )
    await on_confirm_webauth(callback, ConfirmDeeplinkUseCase(store), _Hub(), _USER)  # type: ignore[arg-type]

    assert await store.peek(token) is None  # no longer pending


async def _noop() -> None:
    return None
