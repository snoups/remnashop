from datetime import datetime, timedelta, timezone

from app.core.utils.time import range_end_utc, range_start_utc


def test_range_start_utc_treats_naive_datetime_as_utc() -> None:
    result = range_start_utc(datetime(2026, 8, 18))  # noqa: DTZ001

    assert result == datetime(2026, 8, 18, tzinfo=timezone.utc)


def test_range_start_utc_leaves_aware_datetime_untouched() -> None:
    aware = datetime(2026, 8, 18, 12, tzinfo=timezone(timedelta(hours=5)))

    assert range_start_utc(aware) == aware


def test_range_start_utc_passes_through_none() -> None:
    assert range_start_utc(None) is None


def test_range_end_utc_extends_naive_date_to_end_of_day() -> None:
    result = range_end_utc(datetime(2026, 8, 18))  # noqa: DTZ001

    assert result == datetime(2026, 8, 18, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_range_end_utc_includes_events_after_midnight_on_the_selected_day() -> None:
    date_to = range_end_utc(datetime(2026, 8, 18))  # noqa: DTZ001
    event_late_in_the_day = datetime(2026, 8, 18, 23, 30, tzinfo=timezone.utc)

    assert date_to is not None
    assert event_late_in_the_day <= date_to


def test_range_end_utc_leaves_aware_datetime_untouched() -> None:
    aware = datetime(2026, 8, 18, 12, tzinfo=timezone(timedelta(hours=5)))

    assert range_end_utc(aware) == aware


def test_range_end_utc_passes_through_none() -> None:
    assert range_end_utc(None) is None
