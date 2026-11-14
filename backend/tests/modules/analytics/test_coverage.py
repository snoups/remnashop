from datetime import datetime, timedelta

from app.core.constants import TIMEZONE
from app.core.utils.time import datetime_now
from app.modules.analytics.coverage import is_covered, paid_coverage, shift_months


def test_paid_coverage_merges_early_renewals_and_splits_on_gaps() -> None:
    t0 = datetime_now()
    day = timedelta(days=1)

    assert paid_coverage([(t0, 20), (t0 + 10 * day, 30)]) == [(t0, t0 + 50 * day)]
    assert paid_coverage([(t0, 20), (t0 + 40 * day, 30)]) == [
        (t0, t0 + 20 * day),
        (t0 + 40 * day, t0 + 70 * day),
    ]


def test_is_covered_is_half_open() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=TIMEZONE)
    segments = [(t0, t0 + timedelta(days=30))]
    assert is_covered(segments, t0)
    assert not is_covered(segments, t0 + timedelta(days=30))


def test_shift_months_clamps_the_day() -> None:
    assert shift_months(datetime(2026, 1, 31, 12, tzinfo=TIMEZONE), 1) == datetime(
        2026, 2, 28, 12, tzinfo=TIMEZONE
    )


def test_an_unlimited_payment_covers_far_ahead() -> None:
    t0 = datetime_now()

    segments = paid_coverage([(t0, 0)])

    assert is_covered(segments, t0 + timedelta(days=4000))
