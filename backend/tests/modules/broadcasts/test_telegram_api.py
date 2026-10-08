import json
from pathlib import Path
from typing import Optional

import httpx
import pytest

from app.core.enums import BroadcastMediaType
from app.modules.broadcasts.telegram_api import (
    OutgoingMedia,
    SendOutcome,
    delete_telegram_message,
    send_broadcast_message,
)


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


@pytest.mark.parametrize(
    "status,body,outcome",
    [
        (200, {"ok": True, "result": {"message_id": 5}}, SendOutcome.SENT),
        (
            403,
            {"ok": False, "description": "Forbidden: bot was blocked by the user"},
            SendOutcome.BLOCKED,
        ),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, SendOutcome.FAILED),
        (429, {"ok": False, "parameters": {"retry_after": 3}}, SendOutcome.RETRY),
        (502, {"ok": False}, SendOutcome.RETRY),
        (401, {"ok": False, "description": "Unauthorized"}, SendOutcome.UNAUTHORIZED),
    ],
)
async def test_send_text_outcomes(status: int, body: dict, outcome: SendOutcome) -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    async with _client(httpx.MockTransport(handle)) as client:
        result = await send_broadcast_message(client, "T", 42, "<b>x</b>", None, None)
    assert result.outcome is outcome
    assert seen[0].url.path == "/botT/sendMessage"
    payload = json.loads(seen[0].content)
    assert payload["parse_mode"] == "HTML" and payload["chat_id"] == 42
    if outcome is SendOutcome.RETRY and status == 429:
        assert result.retry_after == 3


async def test_network_error_is_retry() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    async with _client(httpx.MockTransport(handle)) as client:
        result = await send_broadcast_message(client, "T", 1, "x", None, None)
    assert result.outcome is SendOutcome.RETRY


@pytest.mark.parametrize(
    "status,body,retry_after",
    [
        (200, ["not", "a", "dict"], None),
        (429, {"ok": False, "parameters": {"retry_after": "soon"}}, 1.0),
        (429, {"ok": False, "parameters": "nope"}, 1.0),
    ],
)
async def test_malformed_response_is_retry(
    status: int, body: object, retry_after: Optional[float]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    async with _client(httpx.MockTransport(handle)) as client:
        result = await send_broadcast_message(client, "T", 1, "x", None, None)
        deleted = await delete_telegram_message(client, "T", 1, 2)
    assert result.outcome is SendOutcome.RETRY
    assert result.retry_after == retry_after
    assert deleted.outcome is SendOutcome.RETRY


async def test_first_photo_upload_returns_file_id(tmp_path: Path) -> None:
    file = tmp_path / "1.jpg"
    file.write_bytes(b"jpeg")

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/botT/sendPhoto"
        assert b"multipart/form-data" in request.headers["content-type"].encode()
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"message_id": 9, "photo": [{"file_id": "small"}, {"file_id": "big"}]},
            },
        )

    media = OutgoingMedia(
        media_type=BroadcastMediaType.PHOTO, file_id=None, path=file, content_type="image/jpeg"
    )
    async with _client(httpx.MockTransport(handle)) as client:
        result = await send_broadcast_message(client, "T", 1, "cap", {"inline_keyboard": []}, media)
    assert (result.outcome, result.message_id, result.file_id) == (SendOutcome.SENT, 9, "big")


async def test_send_by_file_id_uses_json() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert (
            request.url.path == "/botT/sendVideo"
            and body["video"] == "F"
            and body["caption"] == "c"
        )
        return httpx.Response(
            200, json={"ok": True, "result": {"message_id": 1, "video": {"file_id": "F"}}}
        )

    media = OutgoingMedia(
        media_type=BroadcastMediaType.VIDEO, file_id="F", path=None, content_type=None
    )
    async with _client(httpx.MockTransport(handle)) as client:
        assert (
            await send_broadcast_message(client, "T", 1, "c", None, media)
        ).outcome is SendOutcome.SENT


async def test_delete_message() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": True})

    async with _client(httpx.MockTransport(handle)) as client:
        assert (await delete_telegram_message(client, "T", 1, 2)).outcome is SendOutcome.SENT
