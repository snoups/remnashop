from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final, Optional

from app.core.constants import TIMEZONE
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.time import range_end_utc, range_start_utc

_DEFAULT_DAYS: Final[int] = 30
_MAX_PERIOD_DAYS: Final[int] = 3660
# how far after registration a first payment still counts as a conversion
CONVERSION_WINDOW_DAYS: Final[int] = 7
# the previous window must be representable too
_MIN_INSTANT: Final[datetime] = datetime.min.replace(tzinfo=TIMEZONE)


@dataclass(frozen=True, kw_only=True)
class AnalyticsPeriod:
    start: datetime
    end: datetime

    @property
    def previous(self) -> "AnalyticsPeriod":
        return AnalyticsPeriod(start=self.start - (self.end - self.start), end=self.start)

    @property
    def days(self) -> int:
        return max(1, round((self.end - self.start) / timedelta(days=1)))


def resolve_period(
    period_from: Optional[datetime],
    period_to: Optional[datetime],
    *,
    earliest: Optional[date],
    now: datetime,
) -> AnalyticsPeriod:
    tomorrow = datetime.combine(
        now.astimezone(TIMEZONE).date(), time.min, tzinfo=TIMEZONE
    ) + timedelta(days=1)
    try:
        end = range_end_utc(period_to) or tomorrow
        if period_from is not None:
            start = range_start_utc(period_from)
            assert start is not None
        elif period_to is None:
            start = end - timedelta(days=_DEFAULT_DAYS)
        elif earliest is not None:
            start = datetime.combine(earliest, time.min, tzinfo=TIMEZONE)
        else:
            start = end - timedelta(days=1)
    except OverflowError as error:
        raise ValidationError(
            "Period out of range", code=ErrorCode.ANALYTICS_PERIOD_INVALID
        ) from error

    end = min(end, tomorrow)
    if earliest is not None:
        # an older window than the data would only scan empty days
        first_day = datetime.combine(earliest, time.min, tzinfo=TIMEZONE)
        if first_day < end:
            start = max(start, first_day)
    if start >= end:
        raise ValidationError(
            "period_from must be before period_to", code=ErrorCode.ANALYTICS_PERIOD_INVALID
        )
    # callers reach back a whole previous window plus the conversion window
    reach_back = end - start + timedelta(days=CONVERSION_WINDOW_DAYS)
    if end - start > timedelta(days=_MAX_PERIOD_DAYS) or start - _MIN_INSTANT < reach_back:
        raise ValidationError(
            "Period is longer than the reporting limit", code=ErrorCode.ANALYTICS_PERIOD_INVALID
        )
    return AnalyticsPeriod(start=start, end=end)
