from datetime import datetime, timezone

import httpx
import pytest

from app.modules.settings.telegram_status import fetch_bot_status


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
