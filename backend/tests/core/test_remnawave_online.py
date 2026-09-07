from datetime import date

from app.core.remnawave_online import (
    read_daily_online_peaks,
    read_latest_online,
    record_online_sample,
)

_KEYS = ("remnashop:remnawave:online:latest", "remnashop:remnawave:online:daily_peak")


async def test_record_online_sample_roundtrips_latest_and_daily_peak(redis) -> None:
    await redis.delete(*_KEYS)
    day = date(2026, 1, 1)

    await record_online_sample(redis, day, 10)
    await record_online_sample(redis, day, 25)
    await record_online_sample(redis, day, 15)

    assert await read_latest_online(redis) == 15
    assert await read_daily_online_peaks(redis, [day]) == [(day, 25)]

    await redis.delete(*_KEYS)


async def test_read_daily_online_peaks_skips_days_with_no_sample(redis) -> None:
    await redis.delete(*_KEYS)
    day = date(2026, 1, 1)
    other_day = date(2026, 1, 2)

    await record_online_sample(redis, day, 5)

    assert await read_daily_online_peaks(redis, [day, other_day]) == [(day, 5)]

    await redis.delete(*_KEYS)


async def test_read_latest_online_defaults_to_zero(redis) -> None:
    await redis.delete(*_KEYS)

    assert await read_latest_online(redis) == 0
