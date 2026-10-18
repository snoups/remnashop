import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.constants import REDIS_KEY_PREFIX
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import AnalyticsPeriodQueryDto, CohortsDto


class _DownRedis:
    async def get(self, key: str) -> None:
        raise RedisConnectionError("down")

    async def set(self, *args: object, **kwargs: object) -> None:
        raise RedisConnectionError("down")


async def test_a_repeat_within_the_ttl_comes_from_the_cache(redis: Redis) -> None:
    cache = AnalyticsCache(redis)
    report = f"test-{uuid.uuid4()}"
    params = AnalyticsPeriodQueryDto(period_from=datetime(2026, 1, 1, tzinfo=UTC))
    calls = 0

    async def compute() -> CohortsDto:
        nonlocal calls
        calls += 1
        return CohortsDto(cohorts=[])

    first = await cache.get_or_compute(report, params, CohortsDto, compute)
    second = await cache.get_or_compute(report, params, CohortsDto, compute)
    other = await cache.get_or_compute(report, AnalyticsPeriodQueryDto(), CohortsDto, compute)

    assert first == second == other
    assert calls == 2  # the second call hit the cache, other params did not


async def test_a_stale_cached_payload_is_recomputed(redis: Redis) -> None:
    cache = AnalyticsCache(redis)
    report = f"test-{uuid.uuid4()}"
    key = f"{REDIS_KEY_PREFIX}analytics:{report}:-"
    await redis.set(key, '{"cohorts": "old shape"}', ex=60)

    async def compute() -> CohortsDto:
        return CohortsDto(cohorts=[])

    assert await cache.get_or_compute(report, None, CohortsDto, compute) == CohortsDto(cohorts=[])


async def test_a_redis_outage_still_computes_the_report() -> None:
    cache = AnalyticsCache(_DownRedis())  # type: ignore[arg-type]

    async def compute() -> CohortsDto:
        return CohortsDto(cohorts=[])

    assert await cache.get_or_compute("down", None, CohortsDto, compute) == CohortsDto(cohorts=[])
