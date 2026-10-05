from typing import Any

import pytest
from redis.asyncio import Redis

from app.core.utils.lock import cron_lock
from app.modules.loyalty.dto import RecalculateLoyaltyDto
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task

_run = recalculate_loyalty_discounts_task.original_func.__dishka_orig_func__


class _RecordingUseCase:
    def __init__(self) -> None:
        self.runs: list[RecalculateLoyaltyDto] = []

    @property
    def system(self) -> "_RecordingUseCase":
        return self

    async def __call__(self, data: RecalculateLoyaltyDto) -> int:
        self.runs.append(data)
        return 0


@pytest.fixture
def kicks(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _kiq(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(recalculate_loyalty_discounts_task, "kiq", _kiq)
    return calls


async def test_full_run_blocked_by_another_is_rerun_after_it(
    redis: Redis, kicks: list[dict[str, Any]]
) -> None:
    blocked = _RecordingUseCase()
    async with cron_lock(redis, "loyalty_recalc", ttl_seconds=30) as acquired:
        assert acquired
        await _run(blocked, redis)
        assert blocked.runs == []

    holder = _RecordingUseCase()
    await _run(holder, redis)

    assert holder.runs == [RecalculateLoyaltyDto()]
    assert kicks == [{}]


async def test_full_run_with_nothing_pending_does_not_rerun(
    redis: Redis, kicks: list[dict[str, Any]]
) -> None:
    use_case = _RecordingUseCase()

    await _run(use_case, redis)

    assert use_case.runs == [RecalculateLoyaltyDto()]
    assert kicks == []
