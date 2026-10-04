from datetime import date, datetime, timedelta
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TIMEZONE, TTL_10M

_LATEST_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave:online:latest"
_LATEST_TTL_S: Final[int] = TTL_10M

# Sorted set: member = ISO date, score = that day's peak online count. ZADD's
# GT flag makes "keep the running max per day" a single atomic op instead of
# a read-compare-write race between overlapping sampler ticks.
_DAILY_PEAK_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave:online:daily_peak"


_HOURLY_PEAK_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave:online:hourly_peak"
_HOURLY_KEEP: Final[timedelta] = timedelta(hours=48)


def _hour_member(moment: datetime) -> str:
    return moment.astimezone(TIMEZONE).strftime("%Y-%m-%dT%H")


async def record_online_sample(redis: Redis, moment: datetime, online_now: int) -> None:
    await redis.set(_LATEST_KEY, online_now, ex=_LATEST_TTL_S)
    await redis.zadd(
        _DAILY_PEAK_KEY, {moment.astimezone(TIMEZONE).date().isoformat(): online_now}, gt=True
    )
    await redis.zadd(_HOURLY_PEAK_KEY, {_hour_member(moment): online_now}, gt=True)
    # exact-hour prune, a sampler outage leaves older members;
    # sweep with ZRANGE if the set ever grows
    await redis.zrem(_HOURLY_PEAK_KEY, _hour_member(moment - _HOURLY_KEEP))


async def read_latest_online(redis: Redis) -> int:
    raw = await redis.get(_LATEST_KEY)
    return int(raw) if raw is not None else 0


async def read_daily_online_peaks(redis: Redis, days: list[date]) -> list[tuple[date, int]]:
    if not days:
        return []
    scores = await redis.zmscore(_DAILY_PEAK_KEY, [d.isoformat() for d in days])
    return [(day, int(score)) for day, score in zip(days, scores) if score is not None]


async def read_hourly_online_peaks(redis: Redis, hours: list[datetime]) -> list[Optional[int]]:
    if not hours:
        return []
    scores = await redis.zmscore(_HOURLY_PEAK_KEY, [_hour_member(hour) for hour in hours])
    return [int(score) if score is not None else None for score in scores]
