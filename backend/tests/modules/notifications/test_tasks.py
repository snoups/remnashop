from typing import Any

import pytest
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.exceptions import RetryableTaskError
from app.modules.notifications.tasks import coalesce, deliver, deliver_once


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


async def test_coalesce_suppresses_inside_the_window_and_reports_the_count_after(
    redis: Redis,
) -> None:
    event_type = "LoginFailedEvent"
    await redis.delete(
        f"{REDIS_KEY_PREFIX}notification_window:{event_type}",
        f"{REDIS_KEY_PREFIX}notification_skipped:{event_type}",
    )

    assert await coalesce(redis, event_type) == 0
    assert [await coalesce(redis, event_type) for _ in range(3)] == [None, None, None]
    await redis.delete(f"{REDIS_KEY_PREFIX}notification_window:{event_type}")
    assert await coalesce(redis, event_type) == 3


class FakeUseCase:
    def __init__(self, fail_first: bool = False) -> None:
        self.calls: list[Any] = []
        self._fail = fail_first

    async def system(self, data: Any) -> None:
        self.calls.append(data)
        if self._fail:
            self._fail = False
            raise RetryableTaskError("db down")


async def _reset(redis: Redis, event_type: str) -> None:
    await redis.delete(
        f"{REDIS_KEY_PREFIX}notification_window:{event_type}",
        f"{REDIS_KEY_PREFIX}notification_skipped:{event_type}",
    )


async def _deliver(redis: Redis, use_case: FakeUseCase, outbox_id: int, event_type: str) -> None:
    await deliver(use_case, redis, outbox_id, event_type, {}, None, None)  # type: ignore[arg-type]


async def test_second_coalesced_event_in_window_never_reaches_the_use_case(redis: Redis) -> None:
    await _reset(redis, "LoginFailedEvent")
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 501, "LoginFailedEvent")
    await _deliver(redis, use_case, 502, "LoginFailedEvent")

    assert len(use_case.calls) == 1


async def test_retry_after_a_retryable_failure_keeps_the_alert_and_count(redis: Redis) -> None:
    await _reset(redis, "LoginFailedEvent")
    await coalesce(redis, "LoginFailedEvent")
    await coalesce(redis, "LoginFailedEvent")
    await coalesce(redis, "LoginFailedEvent")
    await redis.delete(f"{REDIS_KEY_PREFIX}notification_window:LoginFailedEvent")
    use_case = FakeUseCase(fail_first=True)

    with pytest.raises(RetryableTaskError):
        await _deliver(redis, use_case, 503, "LoginFailedEvent")
    await _deliver(redis, use_case, 503, "LoginFailedEvent")

    assert [c.suppressed for c in use_case.calls] == [2, 2]


async def test_non_coalesced_events_are_not_throttled(redis: Redis) -> None:
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 504, "BackupFailedEvent")
    await _deliver(redis, use_case, 505, "BackupFailedEvent")

    assert [c.suppressed for c in use_case.calls] == [0, 0]
