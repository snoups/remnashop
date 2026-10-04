from datetime import date, datetime, timedelta, timezone

from app.modules.overview.online import (
    read_daily_online_peaks,
    read_hourly_online_peaks,
    read_latest_online,
    record_online_sample,
)

_KEYS = (
    "remnashop:remnawave:online:latest",
    "remnashop:remnawave:online:daily_peak",
    "remnashop:remnawave:online:hourly_peak",
)


async def test_record_online_sample_roundtrips_latest_and_daily_peak(redis) -> None:
    await redis.delete(*_KEYS)
    day = date(2026, 1, 1)
    moment = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)

    await record_online_sample(redis, moment, 10)
    await record_online_sample(redis, moment, 25)
    await record_online_sample(redis, moment, 15)

    assert await read_latest_online(redis) == 15
    assert await read_daily_online_peaks(redis, [day]) == [(day, 25)]

    await redis.delete(*_KEYS)


async def test_read_daily_online_peaks_skips_days_with_no_sample(redis) -> None:
    await redis.delete(*_KEYS)
    day = date(2026, 1, 1)
    other_day = date(2026, 1, 2)

    await record_online_sample(redis, datetime(2026, 1, 1, 12, tzinfo=timezone.utc), 5)

    assert await read_daily_online_peaks(redis, [day, other_day]) == [(day, 5)]

    await redis.delete(*_KEYS)


async def test_read_latest_online_defaults_to_zero(redis) -> None:
    await redis.delete(*_KEYS)

    assert await read_latest_online(redis) == 0


async def test_hourly_peak_keeps_the_max_per_hour_and_none_for_gaps(redis) -> None:
    await redis.delete(*_KEYS)
    hour = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)

    await record_online_sample(redis, hour + timedelta(minutes=5), 120)
    await record_online_sample(redis, hour + timedelta(minutes=35), 90)

    assert await read_hourly_online_peaks(redis, [hour, hour + timedelta(hours=1)]) == [120, None]

    await redis.delete(*_KEYS)


async def test_record_online_sample_prunes_hours_older_than_48h(redis) -> None:
    await redis.delete(*_KEYS)
    now = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)

    await record_online_sample(redis, old, 7)
    assert await read_hourly_online_peaks(redis, [old]) == [7]
    await record_online_sample(redis, now, 1)

    assert await read_hourly_online_peaks(redis, [old]) == [None]

    await redis.delete(*_KEYS)
