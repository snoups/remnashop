from datetime import timedelta

import httpx
import pytest
from redis.asyncio import Redis

from app.core.panel_writes import PanelWriteRecorder, written_after
from app.core.utils.time import datetime_now


def _recorder(redis: Redis, status_code: int = 200) -> PanelWriteRecorder:
    return PanelWriteRecorder(
        httpx.MockTransport(lambda _request: httpx.Response(status_code)), redis
    )


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/api/users", b'{"id": 5001, "expireAt": "2030-01-01T00:00:00Z"}'),
        ("POST", "/api/users/5001/actions/disable", b""),
        ("POST", "/api/users/5001/actions/reset-traffic", b""),
        ("DELETE", "/api/users/5001", b""),
    ],
)
async def test_a_write_to_a_panel_user_is_marked(
    redis: Redis, method: str, path: str, body: bytes
) -> None:
    before = datetime_now() - timedelta(seconds=1)
    async with httpx.AsyncClient(transport=_recorder(redis), base_url="https://panel") as client:
        await client.request(method, path, content=body)

    assert await written_after(redis, 5001, before)
    assert not await written_after(redis, 5001, datetime_now() + timedelta(seconds=1))


async def test_reads_and_failed_writes_mark_nothing(redis: Redis) -> None:
    before = datetime_now() - timedelta(seconds=1)
    async with httpx.AsyncClient(transport=_recorder(redis), base_url="https://panel") as client:
        await client.get("/api/users/5002")
    async with httpx.AsyncClient(
        transport=_recorder(redis, status_code=404), base_url="https://panel"
    ) as client:
        await client.post("/api/users/5002/actions/enable")

    assert not await written_after(redis, 5002, before)
