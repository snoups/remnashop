from datetime import datetime, timedelta
from decimal import Decimal

from app.core.constants import TIMEZONE
from app.modules.analytics.aggregates import bucket_index, bucket_starts, median
from app.modules.analytics.period import AnalyticsPeriod

START = datetime(2026, 9, 1, tzinfo=TIMEZONE)


def test_median_handles_even_odd_and_empty() -> None:
    assert median([]) == Decimal(0)
    assert median([Decimal(3), Decimal(1), Decimal(2)]) == Decimal(2)
    assert median([Decimal(1), Decimal(4)]) == Decimal("2.5")


def test_day_week_month_buckets() -> None:
    period = AnalyticsPeriod(start=START, end=START + timedelta(days=30))
    assert len(bucket_starts(period, "day")) == 30
    weeks = bucket_starts(period, "week")
    assert weeks[1] == START + timedelta(days=7) and len(weeks) == 5
    months = bucket_starts(
        AnalyticsPeriod(start=START, end=datetime(2026, 11, 15, tzinfo=TIMEZONE)), "month"
    )
    assert months == [
        START,
        datetime(2026, 10, 1, tzinfo=TIMEZONE),
        datetime(2026, 11, 1, tzinfo=TIMEZONE),
    ]


def test_bucket_index_picks_the_last_start_not_after_the_moment() -> None:
    starts = bucket_starts(AnalyticsPeriod(start=START, end=START + timedelta(days=14)), "week")
    assert bucket_index(starts, START + timedelta(days=6, hours=23)) == 0
    assert bucket_index(starts, START + timedelta(days=7)) == 1
