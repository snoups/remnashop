from typing import Any, Optional

import pytest
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.exceptions import RetryableTaskError
from app.modules.notifications.tasks import (
    coalesce,
    coalesce_scope,
    deliver,
    deliver_once,
    flush_coalesced,
)


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


_EVENT = "LoginFailedEvent"
_IP = "203.0.113.1"


def _keys(scope: str) -> list[str]:
    return [
        f"{REDIS_KEY_PREFIX}notification_{part}:{scope}" for part in ("window", "skipped", "last")
    ]


async def _reset(redis: Redis, *scopes: str) -> None:
    # the per-window source count lives in a shared Redis across test runs
    await redis.delete(f"{REDIS_KEY_PREFIX}notification_sources:{_EVENT}")
    for scope in scopes:
        await redis.delete(*_keys(scope))


async def _close_window(redis: Redis, scope: str) -> None:
    await redis.delete(f"{REDIS_KEY_PREFIX}notification_window:{scope}")


def test_scope_falls_back_from_ip_to_login_to_a_dash() -> None:
    assert coalesce_scope(_EVENT, {"login": "bob"}, _IP) == f"{_EVENT}:{_IP}"
    assert coalesce_scope(_EVENT, {"login": "bob"}, None) == f"{_EVENT}:bob"
    assert coalesce_scope(_EVENT, {}, None) == f"{_EVENT}:-"


async def test_coalesce_suppresses_inside_the_window_and_reports_the_count_after(
    redis: Redis,
) -> None:
    scope = coalesce_scope(_EVENT, {}, _IP)
    await _reset(redis, scope)

    assert await coalesce(redis, scope, {}, _IP) == 0
    assert [await coalesce(redis, scope, {}, _IP) for _ in range(3)] == [None, None, None]
    await _close_window(redis, scope)
    assert await coalesce(redis, scope, {}, _IP) == 3


class FakeUseCase:
    def __init__(self, fail_first: bool = False) -> None:
        self.calls: list[Any] = []
        self._fail = fail_first

    async def system(self, data: Any) -> None:
        self.calls.append(data)
        if self._fail:
            self._fail = False
            raise RetryableTaskError("db down")


async def _deliver(
    redis: Redis,
    use_case: FakeUseCase,
    outbox_id: int,
    event_type: str,
    ip_address: str = _IP,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    await deliver(use_case, redis, outbox_id, event_type, payload or {}, None, ip_address)  # type: ignore[arg-type]


async def test_second_coalesced_event_in_window_never_reaches_the_use_case(redis: Redis) -> None:
    await _reset(redis, coalesce_scope(_EVENT, {}, _IP))
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 501, _EVENT)
    await _deliver(redis, use_case, 502, _EVENT)

    assert len(use_case.calls) == 1


async def test_failures_from_different_sources_each_alert(redis: Redis) -> None:
    other = "203.0.113.2"
    await _reset(redis, coalesce_scope(_EVENT, {}, _IP), coalesce_scope(_EVENT, {}, other))
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 511, _EVENT, _IP)
    await _deliver(redis, use_case, 512, _EVENT, other)

    assert [c.ip_address for c in use_case.calls] == [_IP, other]


async def test_retry_after_a_retryable_failure_keeps_the_alert_and_count(redis: Redis) -> None:
    scope = coalesce_scope(_EVENT, {}, _IP)
    await _reset(redis, scope)
    for _ in range(3):
        await coalesce(redis, scope, {}, _IP)
    await _close_window(redis, scope)
    use_case = FakeUseCase(fail_first=True)

    with pytest.raises(RetryableTaskError):
        await _deliver(redis, use_case, 503, _EVENT)
    await _deliver(redis, use_case, 503, _EVENT)

    assert [c.suppressed for c in use_case.calls] == [2, 2]


async def test_non_coalesced_events_are_not_throttled(redis: Redis) -> None:
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 504, "BackupFailedEvent")
    await _deliver(redis, use_case, 505, "BackupFailedEvent")

    assert [c.suppressed for c in use_case.calls] == [0, 0]


async def test_a_burst_that_ends_is_summarised_once_its_window_closes(redis: Redis) -> None:
    scope = coalesce_scope(_EVENT, {}, _IP)
    await _reset(redis, scope)
    use_case = FakeUseCase()
    await _deliver(redis, use_case, 521, _EVENT, payload={"login": "a"})
    await _deliver(redis, use_case, 522, _EVENT, payload={"login": "b"})
    await _deliver(redis, use_case, 523, _EVENT, payload={"login": "c"})

    assert await flush_coalesced(redis, use_case) == 0  # window still open
    await _close_window(redis, scope)
    assert await flush_coalesced(redis, use_case) == 1
    assert await flush_coalesced(redis, use_case) == 0

    summary = use_case.calls[-1]
    assert summary.event_type == _EVENT
    assert summary.payload == {"login": "c"} and summary.ip_address == _IP
    assert summary.suppressed == 1


async def test_sources_past_the_cap_fold_into_one_overflow_alert(redis: Redis) -> None:
    ips = [f"198.51.100.{i}" for i in range(8)]
    await _reset(redis, *(coalesce_scope(_EVENT, {}, ip) for ip in ips), f"{_EVENT}:*")
    use_case = FakeUseCase()

    for outbox_id, ip in enumerate(ips, start=600):
        await _deliver(redis, use_case, outbox_id, _EVENT, ip)

    # five sources alert on their own, the rest share one overflow window
    assert [c.ip_address for c in use_case.calls] == ips[:6]
    assert [c.sources_merged for c in use_case.calls] == [False] * 5 + [True]


async def test_a_source_counter_left_without_ttl_gets_one(redis: Redis) -> None:
    ip = "198.51.100.200"
    await _reset(redis, coalesce_scope(_EVENT, {}, ip))
    counter = f"{REDIS_KEY_PREFIX}notification_sources:{_EVENT}"
    # a worker killed between counting and expiring left this behind
    await redis.set(counter, 1)
    use_case = FakeUseCase()

    await _deliver(redis, use_case, 700, _EVENT, ip)

    assert await redis.ttl(counter) > 0
