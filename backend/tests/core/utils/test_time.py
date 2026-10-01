from datetime import datetime, timedelta, timezone

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.utils.time import (
    datetime_now,
    get_traffic_reset_delta,
    range_end_utc,
    range_start_utc,
)


def test_range_start_utc_treats_naive_datetime_as_utc() -> None:
    result = range_start_utc(datetime(2026, 8, 18))  # noqa: DTZ001

    assert result == datetime(2026, 8, 18, tzinfo=timezone.utc)


def test_range_start_utc_leaves_aware_datetime_untouched() -> None:
    aware = datetime(2026, 8, 18, 12, tzinfo=timezone(timedelta(hours=5)))

    assert range_start_utc(aware) == aware


def test_range_start_utc_passes_through_none() -> None:
    assert range_start_utc(None) is None


def test_range_end_utc_moves_naive_date_to_next_midnight() -> None:
    result = range_end_utc(datetime(2026, 8, 18))  # noqa: DTZ001

    assert result == datetime(2026, 8, 19, tzinfo=timezone.utc)


def test_range_end_utc_includes_the_whole_selected_day_exclusively() -> None:
    date_to = range_end_utc(datetime(2026, 8, 18))  # noqa: DTZ001
    event_late_in_the_day = datetime(2026, 8, 18, 23, 30, tzinfo=timezone.utc)
    next_midnight = datetime(2026, 8, 19, tzinfo=timezone.utc)

    assert date_to is not None
    assert event_late_in_the_day < date_to
    assert not next_midnight < date_to


def test_range_end_utc_leaves_aware_datetime_untouched() -> None:
    aware = datetime(2026, 8, 18, 12, tzinfo=timezone(timedelta(hours=5)))

    assert range_end_utc(aware) == aware


def test_range_end_utc_passes_through_none() -> None:
    assert range_end_utc(None) is None


def test_get_traffic_reset_delta_no_reset() -> None:
    result = get_traffic_reset_delta(TrafficLimitStrategy.NO_RESET, datetime_now())

    assert result == timedelta(seconds=0)


def test_get_traffic_reset_delta_day_within_range() -> None:
    created_at = datetime_now() - timedelta(hours=5)

    result = get_traffic_reset_delta(TrafficLimitStrategy.DAY, created_at)

    assert timedelta(0) < result <= timedelta(days=1)


def test_get_traffic_reset_delta_week_within_range() -> None:
    created_at = datetime_now() - timedelta(days=2)

    result = get_traffic_reset_delta(TrafficLimitStrategy.WEEK, created_at)

    assert timedelta(0) < result <= timedelta(days=7)


def test_get_traffic_reset_delta_month_within_range() -> None:
    created_at = datetime_now() - timedelta(days=10)

    result = get_traffic_reset_delta(TrafficLimitStrategy.MONTH, created_at)

    assert timedelta(0) < result <= timedelta(days=30)


def test_get_traffic_reset_delta_unhandled_strategy_raises() -> None:
    with pytest.raises(ValueError, match="Unhandled TrafficLimitStrategy"):
        get_traffic_reset_delta(TrafficLimitStrategy.MONTH_ROLLING, datetime_now())
