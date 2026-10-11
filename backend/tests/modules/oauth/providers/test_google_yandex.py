from typing import Any, Optional

import pytest

from app.modules.oauth.providers import google, yandex
from app.modules.oauth.providers.base import OAuthProfile


class _Response:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]:
        return self._data


def _fake_client(data: dict[str, Any]) -> type:
    class _Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: Any) -> None: ...

        async def fetch_token(self, *args: Any, **kwargs: Any) -> dict[str, str]:
            return {"access_token": "tok"}

        async def get(self, *args: Any, **kwargs: Any) -> _Response:
            return _Response(data)

    return _Client


async def _google(monkeypatch: pytest.MonkeyPatch, data: dict[str, Any]) -> OAuthProfile:
    monkeypatch.setattr(google, "AsyncOAuth2Client", _fake_client(data))
    return await google.GoogleOAuthClient("id", "secret").fetch_identity("https://x/cb", "c", "v")


async def _yandex(monkeypatch: pytest.MonkeyPatch, data: dict[str, Any]) -> OAuthProfile:
    monkeypatch.setattr(yandex, "AsyncOAuth2Client", _fake_client(data))
    return await yandex.YandexOAuthClient("id", "secret").fetch_identity("https://x/cb", "c", "v")


@pytest.mark.parametrize(("verified", "expected"), [(True, True), (False, False), (None, False)])
async def test_google_profile(
    monkeypatch: pytest.MonkeyPatch, verified: Optional[bool], expected: bool
) -> None:
    profile = await _google(
        monkeypatch,
        {
            "sub": "g1",
            "email": "A@B.c",
            "email_verified": verified,
            "name": "Ann",
            "locale": "ru",
        },
    )
    assert profile == OAuthProfile(
        external_id="g1",
        login="A@B.c",
        name="Ann",
        email="A@B.c",
        email_verified=expected,
        language="ru",
    )


async def test_yandex_profile_with_email(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = await _yandex(
        monkeypatch,
        {"id": "y1", "login": "ann", "default_email": "ann@yandex.ru", "real_name": "Ann"},
    )
    assert profile == OAuthProfile(
        external_id="y1",
        login="ann",
        name="Ann",
        email="ann@yandex.ru",
        email_verified=True,
    )


async def test_yandex_profile_without_email(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = await _yandex(monkeypatch, {"id": "y1", "login": "ann"})
    assert profile.email is None and profile.email_verified is False
