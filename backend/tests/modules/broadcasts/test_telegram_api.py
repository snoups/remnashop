from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.enums import BroadcastMediaType
from app.core.telegram_api import BotApiError
from app.modules.broadcasts.telegram_api import (
    OutgoingMedia,
    SendOutcome,
    delete_telegram_message,
    send_broadcast_message,
)
from tests.modules.broadcasts.factories import BotRequest, MockTelegram, message_result

_TOKEN = "123:abc"


def _reply(status: int, body: object) -> Any:
    return lambda method: httpx.Response(status, json=body)


@pytest.mark.parametrize(
    "status,body,outcome",
    [
        (200, {"ok": True, "result": message_result(5)}, SendOutcome.SENT),
        (
            403,
            {"ok": False, "description": "Forbidden: bot was blocked by the user"},
            SendOutcome.BLOCKED,
        ),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, SendOutcome.FAILED),
        (
            429,
            {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}},
            SendOutcome.RETRY,
        ),
        (502, {"ok": False, "description": "Bad Gateway"}, SendOutcome.RETRY),
        (401, {"ok": False, "description": "Unauthorized"}, SendOutcome.UNAUTHORIZED),
    ],
)
async def test_send_text_outcomes(status: int, body: dict, outcome: SendOutcome) -> None:
    telegram = MockTelegram(_reply(status, body))

    async with telegram.open(_TOKEN, None) as bot:
        result = await send_broadcast_message(bot, 42, "<b>x</b>", None, None)

    assert result.outcome is outcome
    [sent] = telegram.requests
    assert sent.method == "sendMessage"
    assert (sent.params["chat_id"], sent.params["parse_mode"]) == (42, "HTML")
    if status == 429:
        assert result.retry_after == 3


async def test_network_error_is_retry() -> None:
    def _down(request: BotRequest) -> httpx.Response:
        raise BotApiError("sendMessage: ServerTimeoutError")

    async with MockTelegram(_down).open(_TOKEN, None) as bot:
        result = await send_broadcast_message(bot, 1, "x", None, None)

    assert result.outcome is SendOutcome.RETRY


@pytest.mark.parametrize(
    "status,body",
    [
        (200, ["not", "a", "dict"]),
        (429, {"ok": False, "parameters": {"retry_after": "soon"}}),
        (429, {"ok": False, "parameters": "nope"}),
    ],
)
async def test_malformed_response_is_retry(status: int, body: object) -> None:
    async with MockTelegram(_reply(status, body)).open(_TOKEN, None) as bot:
        result = await send_broadcast_message(bot, 1, "x", None, None)
        deleted = await delete_telegram_message(bot, 1, 2)

    assert result.outcome is SendOutcome.RETRY
    # an unreadable flood wait is an ordinary failed attempt
    assert result.retry_after is None
    assert deleted.outcome is SendOutcome.RETRY


async def test_first_photo_upload_returns_file_id(tmp_path: Path) -> None:
    file = tmp_path / "1.jpg"
    file.write_bytes(b"jpeg")
    photo = [
        {"file_id": "small", "file_unique_id": "s", "width": 1, "height": 1},
        {"file_id": "big", "file_unique_id": "b", "width": 2, "height": 2},
    ]
    telegram = MockTelegram(_reply(200, {"ok": True, "result": message_result(9, photo=photo)}))
    media = OutgoingMedia(
        media_type=BroadcastMediaType.PHOTO, file_id=None, path=file, content_type="image/jpeg"
    )

    async with telegram.open(_TOKEN, None) as bot:
        result = await send_broadcast_message(bot, 1, "cap", {"inline_keyboard": []}, media)

    assert (result.outcome, result.message_id, result.file_id) == (SendOutcome.SENT, 9, "big")
    [sent] = telegram.requests
    assert sent.method == "sendPhoto" and sent.params["photo"] == file


async def test_a_missing_media_file_is_not_a_network_failure(tmp_path: Path) -> None:
    media = OutgoingMedia(
        media_type=BroadcastMediaType.PHOTO,
        file_id=None,
        path=tmp_path / "gone.jpg",
        content_type="image/jpeg",
    )

    async with MockTelegram(_reply(200, {})).open(_TOKEN, None) as bot:
        with pytest.raises(FileNotFoundError):
            await send_broadcast_message(bot, 1, "cap", None, media)


async def test_send_by_file_id_reuses_the_upload() -> None:
    video = {"file_id": "F", "file_unique_id": "u", "width": 1, "height": 1, "duration": 1}
    telegram = MockTelegram(_reply(200, {"ok": True, "result": message_result(1, video=video)}))
    media = OutgoingMedia(
        media_type=BroadcastMediaType.VIDEO, file_id="F", path=None, content_type=None
    )

    async with telegram.open(_TOKEN, None) as bot:
        result = await send_broadcast_message(bot, 1, "c", None, media)

    assert (result.outcome, result.file_id) == (SendOutcome.SENT, "F")
    [sent] = telegram.requests
    assert sent.method == "sendVideo"
    assert (sent.params["video"], sent.params["caption"]) == ("F", "c")


async def test_delete_message() -> None:
    telegram = MockTelegram(_reply(200, {"ok": True, "result": True}))

    async with telegram.open(_TOKEN, None) as bot:
        assert (await delete_telegram_message(bot, 1, 2)).outcome is SendOutcome.SENT

    [sent] = telegram.requests
    assert sent.method == "deleteMessage"
    assert (sent.params["chat_id"], sent.params["message_id"]) == (1, 2)
