from datetime import datetime, timedelta, timezone

import pytest

from app.modules.transactions.recurring_policy import RETRY_OFFSETS_HOURS, retry_at

_FIRST_FAILURE = datetime(2026, 11, 14, 9, 17, 23, tzinfo=timezone.utc)


def test_bank_retry_schedule_is_anchored_to_the_first_failure() -> None:
    # These are absolute offsets, not increasing delays after each failed retry.
    expected = (1, 3, 6, 12, 24, 36, 48, 72)
    assert RETRY_OFFSETS_HOURS == expected
    scheduled = tuple(retry_at(_FIRST_FAILURE, index) for index in range(8))
    assert scheduled == tuple(_FIRST_FAILURE + timedelta(hours=hour) for hour in expected)


@pytest.mark.parametrize("retry_count", [-1, 8, 9, 1000])
def test_a_retry_outside_the_schedule_is_not_created(retry_count: int) -> None:
    assert retry_at(_FIRST_FAILURE, retry_count) is None


def test_retries_keep_the_original_timezone_and_cross_date_boundaries() -> None:
    first_failure = datetime(2026, 11, 14, 23, 45, tzinfo=timezone(timedelta(hours=3)))
    scheduled = retry_at(first_failure, 7)
    assert scheduled is not None
    assert scheduled == datetime(2026, 11, 17, 23, 45, tzinfo=first_failure.tzinfo)
    assert scheduled.tzinfo is first_failure.tzinfo
