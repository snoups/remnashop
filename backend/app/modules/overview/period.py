import operator
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final, TypeVar

from app.core.enums import Role
from app.core.utils.time import datetime_now
from app.modules.overview.dto import Granularity
from app.modules.users import UserStatsRepository

_T = TypeVar("_T", int, Decimal)

# daily below this span, monthly above; no weekly step
_MONTHLY_THRESHOLD_DAYS: Final[int] = 90


def _iter_months(start: date, end: date) -> Iterator[date]:
    cur = start.replace(day=1)
    last = end.replace(day=1)
    while cur <= last:
        yield cur
        cur = (cur + timedelta(days=32)).replace(day=1)


@dataclass(frozen=True, kw_only=True)
class Period:
    today_start: datetime
    start_date: date
    today: date
    since: datetime
    granularity: Granularity
    dense: bool

    def days(self) -> list[date]:
        return [
            self.start_date + timedelta(days=i)
            for i in range((self.today - self.start_date).days + 1)
        ]

    def bucketize(
        self,
        rows: list[tuple[date, _T]],
        zero: _T,
        op: Callable[[_T, _T], _T] = operator.add,
    ) -> list[tuple[date, _T]]:
        if self.granularity == "month":
            acc: dict[date, _T] = dict.fromkeys(_iter_months(self.start_date, self.today), zero)
            for day, value in rows:
                key = day.replace(day=1)
                acc[key] = op(acc[key], value)
            return sorted(acc.items())
        if not self.dense:
            return rows
        acc = dict.fromkeys(self.days(), zero)
        for day, value in rows:
            acc[day] = op(acc[day], value)
        return sorted(acc.items())


async def resolve_period(user_stats: UserStatsRepository, days: int) -> Period:
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = today_start.date()
    if days == 0:
        first_registration = await user_stats.earliest_registration(Role.USER)
        start_date = first_registration or today
    else:
        start_date = today - timedelta(days=days - 1)
    span_days = (today - start_date).days + 1
    return Period(
        today_start=today_start,
        start_date=start_date,
        today=today,
        # calendar days, like the frontend's fillDailySeries (`days` UTC days
        # ending today); a rolling cutoff would add a partial first day and
        # the daily series wouldn't sum to the card totals
        since=today_start - timedelta(days=span_days - 1),
        granularity="month" if span_days > _MONTHLY_THRESHOLD_DAYS else "day",
        dense=days == 0,
    )
