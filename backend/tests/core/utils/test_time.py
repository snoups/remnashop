from datetime import datetime, timedelta, timezone

from app.core.utils.time import (
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


def test_range_end_utc_keeps_a_naive_time_of_day() -> None:
    result = range_end_utc(datetime(2026, 8, 18, 15, 0))  # noqa: DTZ001

    assert result == datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)
