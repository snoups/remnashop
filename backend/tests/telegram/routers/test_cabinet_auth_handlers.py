from types import SimpleNamespace
from typing import Any, Optional

import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import TTL_5M
from app.core.enums import Locale
from app.modules.cabinet_auth import DeeplinkStore, InviteCodesDto, IssueBotSignInLinkUseCase
from app.telegram.routers.cabinet_auth import handlers
from app.telegram.routers.cabinet_auth.handlers import on_start_webauth


class _Runner:
    def get(self, key: str, **kwargs: Any) -> str:
        return key


class _Hub:
    translators_map = {"en": [], "ru": []}
    root_locale = "en"

    def __init__(self) -> None:
        self.locales: list[str] = []

    def get_translator_by_locale(self, locale: str) -> _Runner:
        self.locales.append(locale)
        return _Runner()


class _Message:
    def __init__(self, text: str, telegram_id: int = 9, language_code: str = "en") -> None:
        self.text = text
        self.from_user = SimpleNamespace(
            id=telegram_id, full_name="Ann", username="ann", language_code=language_code
        )
        self.sent: list[dict[str, Any]] = []

    async def answer(self, text: str, reply_markup: Optional[Any] = None) -> dict[str, Any]:
        sent = {"text": text, "markup": reply_markup}
        self.sent.append(sent)
        return sent


_USER: Any = SimpleNamespace(language=Locale.EN)


@pytest.fixture(autouse=True)
def deletions(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, int]]:
    scheduled: list[tuple[Any, int]] = []
    monkeypatch.setattr(
        handlers, "delete_later", lambda sent, seconds: scheduled.append((sent, seconds))
    )
    return scheduled


async def test_start_sends_a_one_time_sign_in_button(
    redis: Redis, config: AppConfig, monkeypatch: Any, deletions: list[tuple[Any, int]]
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    store = DeeplinkStore(redis)
    start = await store.create(InviteCodesDto())
    message = _Message(f"/start webauth_{start}")

    await on_start_webauth(
        message, IssueBotSignInLinkUseCase(store, config), _Hub(), _USER, config=config
    )  # type: ignore[arg-type]

    assert message.sent[0]["text"] == "ntf-cabinet-login.link"
    button = message.sent[0]["markup"].inline_keyboard[0][0]
    assert button.text == "btn-cabinet-login.open-icon btn-cabinet-login.open"
    assert button.url.startswith("https://cabinet.example.com/login/bot#token=")
    signin = button.url.split("token=", 1)[1]
    grant = await store.take_signin(signin)
    assert grant is not None and grant.profile.telegram_id == 9
    # the button goes with the link's own lifetime
    assert deletions == [(message.sent[0], TTL_5M)]


async def test_second_start_with_the_same_link_says_expired(
    redis: Redis, config: AppConfig, monkeypatch: Any
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    store = DeeplinkStore(redis)
    start = await store.create(InviteCodesDto())
    issue = IssueBotSignInLinkUseCase(store, config)

    await on_start_webauth(_Message(f"/start webauth_{start}"), issue, _Hub(), _USER, config=config)  # type: ignore[arg-type]
    again = _Message(f"/start webauth_{start}")
    await on_start_webauth(again, issue, _Hub(), _USER, config=config)  # type: ignore[arg-type]

    assert again.sent[0]["text"] == "ntf-cabinet-login.expired"
    assert again.sent[0]["markup"] is None


async def test_start_with_unknown_token_says_expired(
    redis: Redis, config: AppConfig, monkeypatch: Any
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    message = _Message("/start webauth_" + "x" * 43)

    await on_start_webauth(
        message,
        IssueBotSignInLinkUseCase(DeeplinkStore(redis), config),
        _Hub(),
        _USER,  # type: ignore[arg-type]
        config=config,
    )

    assert message.sent[0]["text"] == "ntf-cabinet-login.expired"


async def test_start_without_a_cabinet_url_sends_no_button(
    redis: Redis, config: AppConfig, monkeypatch: Any
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", None)
    store = DeeplinkStore(redis)
    start = await store.create(InviteCodesDto())
    message = _Message(f"/start webauth_{start}")

    await on_start_webauth(
        message, IssueBotSignInLinkUseCase(store, config), _Hub(), _USER, config=config
    )  # type: ignore[arg-type]

    assert message.sent[0]["text"] == "ntf-cabinet-login.unavailable"
    assert message.sent[0]["markup"] is None
    # the start link isn't spent by a misconfigured cabinet
    assert await store.peek(start) is not None


async def test_link_start_without_an_account_answers_in_the_telegram_language(
    redis: Redis, config: AppConfig, monkeypatch: Any
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    store = DeeplinkStore(redis)
    issue = IssueBotSignInLinkUseCase(store, config)

    hub = _Hub()
    message = _Message(
        f"/start webauth_{await store.create(InviteCodesDto(), link_user_id=1)}",
        language_code="ru-RU",
    )
    await on_start_webauth(message, issue, hub, None, config=config)  # type: ignore[arg-type]
    assert hub.locales == ["ru"]
    button = message.sent[0]["markup"].inline_keyboard[0][0]
    assert button.url.startswith("https://cabinet.example.com/link/bot#token=")

    # a locale the bot doesn't serve falls back to the root one
    fallback = _Hub()
    other = _Message(
        f"/start webauth_{await store.create(InviteCodesDto(), link_user_id=1)}", language_code="de"
    )
    await on_start_webauth(other, issue, fallback, None, config=config)  # type: ignore[arg-type]
    assert fallback.locales == ["en"]


async def test_link_start_sends_the_linking_wording(
    redis: Redis, config: AppConfig, monkeypatch: Any
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    store = DeeplinkStore(redis)
    start = await store.create(InviteCodesDto(), link_user_id=42)
    message = _Message(f"/start webauth_{start}")

    await on_start_webauth(
        message, IssueBotSignInLinkUseCase(store, config), _Hub(), _USER, config=config
    )  # type: ignore[arg-type]

    assert message.sent[0]["text"] == "ntf-cabinet-link.link"
    button = message.sent[0]["markup"].inline_keyboard[0][0]
    assert button.text == "btn-cabinet-link.open-icon btn-cabinet-link.open"
    assert button.url.startswith("https://cabinet.example.com/link/bot#token=")
