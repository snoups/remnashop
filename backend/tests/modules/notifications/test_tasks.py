import pytest
from redis.asyncio import Redis

from app.core.exceptions import RetryableTaskError
from app.modules.notifications.tasks import deliver_once


async def test_second_delivery_of_the_same_outbox_row_is_skipped(redis: Redis) -> None:
    runs: list[int] = []

    async def run() -> None:
        runs.append(1)

    await deliver_once(redis, 41, run)
    await deliver_once(redis, 41, run)

    assert runs == [1]


async def test_a_retryable_failure_releases_the_row_for_the_retry(redis: Redis) -> None:
    attempts: list[int] = []

    async def failing() -> None:
        attempts.append(1)
        raise RetryableTaskError("db down")

    async def succeeding() -> None:
        attempts.append(2)

    with pytest.raises(RetryableTaskError):
        await deliver_once(redis, 42, failing)
    await deliver_once(redis, 42, succeeding)

    assert attempts == [1, 2]


async def test_an_unexpected_failure_keeps_the_row_taken(redis: Redis) -> None:
    attempts: list[int] = []

    async def broken() -> None:
        attempts.append(1)
        raise RuntimeError("after some sends")

    with pytest.raises(RuntimeError):
        await deliver_once(redis, 43, broken)
    await deliver_once(redis, 43, broken)

    assert attempts == [1]
