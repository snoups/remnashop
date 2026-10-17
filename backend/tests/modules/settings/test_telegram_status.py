from datetime import datetime, timezone

import httpx
import pytest

from app.modules.settings import telegram_status
from app.modules.settings.telegram_status import fetch_bot_status, fetch_bot_username


async def test_non_json_reply_becomes_a_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)

    status = await fetch_bot_status("token", None)

    assert status.is_configured is True
    assert status.error


async def test_last_error_date_becomes_a_utc_datetime(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "url": "https://x",
                    "last_error_message": "boom",
                    "last_error_date": 1_700_000_000,
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)

    status = await fetch_bot_status("token", None)

    assert status.last_error_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clean_username_caches() -> None:
    telegram_status._USERNAME_CACHE.clear()
    telegram_status._USERNAME_FAILED_UNTIL.clear()


async def test_a_failed_username_lookup_is_not_retried_inside_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    now = 1000.0

    async def _get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("down")

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    monkeypatch.setattr(telegram_status.time, "monotonic", lambda: now)

    assert await fetch_bot_username("token", None) is None
    assert await fetch_bot_username("token", None) is None
    assert calls == 1

    now += 61
    assert await fetch_bot_username("token", None) is None
    assert calls == 2


async def test_a_malformed_ok_payload_gives_no_username(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)

    assert await fetch_bot_username("token", None) is None
