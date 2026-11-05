from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import pytest
from remnapy import RemnawaveSDK

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.panel import PanelIndex, assert_panel_v3, fetch_panel_index, resolve_panel_id
from tests.fakes.remnawave import _user_payload, make_fake_remnawave_transport


def _sdk(transport: httpx.MockTransport) -> RemnawaveSDK:
    return RemnawaveSDK(
        client=httpx.AsyncClient(transport=transport, base_url="http://fake-panel.test/api")
    )


def _put(
    store: dict[int, dict[str, Any]], user_id: int, username: str, telegram_id: Optional[int] = None
) -> None:
    payload = _user_payload(
        user_id=user_id, username=username, expire_at=datetime(2030, 1, 1, tzinfo=timezone.utc)
    )
    payload["telegramId"] = telegram_id
    payload["shortUuid"] = f"s{user_id}"
    store[user_id] = payload


async def test_fetch_panel_index_follows_cursor() -> None:
    store: dict[int, dict[str, Any]] = {}
    for user_id in range(1, 2501):
        _put(store, user_id, f"u{user_id}")
    requests: list[str] = []
    transport, _, _ = make_fake_remnawave_transport(store)
    inner = transport.handler

    def counting(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/users/stream":
            requests.append(str(request.url))
        return inner(request)  # type: ignore[return-value]

    index = await fetch_panel_index(_sdk(httpx.MockTransport(counting)), page_size=1000)

    assert len(requests) == 3
    assert len(index.by_username) == 2500
    assert index.by_short_uuid["s7"] == 7


def _index() -> PanelIndex:
    return PanelIndex(
        by_short_uuid={"abc123XYZ": 5},
        by_username={"rs_777": 6, "rs_web_42": 7, "other": 5},
        by_telegram_id={900: [8], 901: [9, 10]},
    )


def test_resolve_by_short_uuid() -> None:
    found = resolve_panel_id(
        url="https://sub.example.com/abc123XYZ", telegram_id=777, user_id=1, index=_index()
    )
    assert found == (5, "shortUuid")


def test_resolve_by_legacy_username() -> None:
    assert resolve_panel_id(url=None, telegram_id=777, user_id=1, index=_index())[0] == 6
    assert (
        resolve_panel_id(url="https://x/none", telegram_id=None, user_id=42, index=_index())[0] == 7
    )


def test_resolve_by_unique_telegram_id() -> None:
    assert resolve_panel_id(url=None, telegram_id=900, user_id=1, index=_index())[0] == 8


def test_ambiguous_telegram_id_not_resolved() -> None:
    found, reason = resolve_panel_id(url=None, telegram_id=901, user_id=1, index=_index())
    assert found is None
    assert "901" in reason


async def test_assert_panel_v3_rejects_2x() -> None:
    transport, _, _ = make_fake_remnawave_transport(panel_version="2.3.1")
    with pytest.raises(LegacyMigrationError, match="3.x"):
        await assert_panel_v3(_sdk(transport))


async def test_assert_panel_v3_accepts_3x() -> None:
    transport, _, _ = make_fake_remnawave_transport(panel_version="3.0.1")
    await assert_panel_v3(_sdk(transport))
