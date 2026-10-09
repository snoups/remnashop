# ruff: noqa: DTZ001  # bare dates arrive naive by design
from datetime import date, datetime, timedelta

import pytest

from app.core.constants import TIMEZONE
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.analytics.period import AnalyticsPeriod, resolve_period

NOW = datetime(2026, 10, 4, 15, 30, tzinfo=TIMEZONE)
TODAY_START = datetime(2026, 10, 4, tzinfo=TIMEZONE)


def test_default_is_last_30_days_including_today() -> None:
    period = resolve_period(None, None, earliest=None, now=NOW)
    assert period.end == TODAY_START + timedelta(days=1)
    assert period.start == period.end - timedelta(days=30)
    assert period.days == 30


def test_bare_dates_cover_whole_days() -> None:
    period = resolve_period(datetime(2026, 9, 1), datetime(2026, 9, 30), earliest=None, now=NOW)
    assert period.start == datetime(2026, 9, 1, tzinfo=TIMEZONE)
    assert period.end == datetime(2026, 10, 1, tzinfo=TIMEZONE)
    assert period.previous == AnalyticsPeriod(
        start=datetime(2026, 8, 2, tzinfo=TIMEZONE), end=datetime(2026, 9, 1, tzinfo=TIMEZONE)
    )


def test_only_period_to_means_all_time_from_first_registration() -> None:
    period = resolve_period(None, datetime(2026, 10, 4), earliest=date(2026, 3, 15), now=NOW)
    assert period.start == datetime(2026, 3, 15, tzinfo=TIMEZONE)


def test_all_time_on_an_empty_database_is_one_day() -> None:
    period = resolve_period(None, datetime(2026, 10, 4), earliest=None, now=NOW)
    assert period.days == 1


def test_from_after_to_is_rejected() -> None:
    with pytest.raises(ValidationError):
        resolve_period(datetime(2026, 10, 2), datetime(2026, 10, 1), earliest=None, now=NOW)


def test_far_period_to_is_clamped_to_tomorrow() -> None:
    period = resolve_period(datetime(2026, 9, 1), datetime(9999, 12, 30), earliest=None, now=NOW)

    assert period.end == TODAY_START + timedelta(days=1)


def test_period_starting_after_tomorrow_is_invalid() -> None:
    with pytest.raises(ValidationError) as error:
        resolve_period(
            datetime(5001, 1, 1), datetime(9999, 12, 30), earliest=date(2026, 1, 1), now=NOW
        )

    assert error.value.code is ErrorCode.ANALYTICS_PERIOD_INVALID


def test_far_period_from_is_clamped_to_first_registration() -> None:
    period = resolve_period(datetime(1900, 1, 1), None, earliest=date(2026, 1, 1), now=NOW)

    assert period.start == datetime(2026, 1, 1, tzinfo=TIMEZONE)


def test_last_representable_day_is_invalid_not_overflow() -> None:
    with pytest.raises(ValidationError) as error:
        resolve_period(None, datetime(9999, 12, 31), earliest=None, now=NOW)

    assert error.value.code is ErrorCode.ANALYTICS_PERIOD_INVALID


def test_span_beyond_the_ceiling_is_invalid() -> None:
    with pytest.raises(ValidationError) as error:
        resolve_period(datetime(1900, 1, 1), None, earliest=None, now=NOW)

    assert error.value.code is ErrorCode.ANALYTICS_PERIOD_INVALID


def test_window_whose_previous_window_is_unrepresentable_is_invalid() -> None:
    with pytest.raises(ValidationError) as error:
        resolve_period(datetime(1, 1, 2), datetime(1, 1, 10), earliest=None, now=NOW)

    assert error.value.code is ErrorCode.ANALYTICS_PERIOD_INVALID
