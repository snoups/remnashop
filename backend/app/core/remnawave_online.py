from datetime import date
from typing import Final

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX

_LATEST_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave:online:latest"
_LATEST_TTL_S: Final[int] = 600

# Sorted set: member = ISO date, score = that day's peak online count. ZADD's
# GT flag makes "keep the running max per day" a single atomic op instead of
# a read-compare-write race between overlapping sampler ticks.
_DAILY_PEAK_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave:online:daily_peak"


async def record_online_sample(redis: Redis, day: date, online_now: int) -> None:
    await redis.set(_LATEST_KEY, online_now, ex=_LATEST_TTL_S)
    await redis.zadd(_DAILY_PEAK_KEY, {day.isoformat(): online_now}, gt=True)


async def read_latest_online(redis: Redis) -> int:
    raw = await redis.get(_LATEST_KEY)
    return int(raw) if raw is not None else 0


async def read_daily_online_peaks(redis: Redis, days: list[date]) -> list[tuple[date, int]]:
    if not days:
        return []
    scores = await redis.zmscore(_DAILY_PEAK_KEY, [d.isoformat() for d in days])
    return [(day, int(score)) for day, score in zip(days, scores) if score is not None]
