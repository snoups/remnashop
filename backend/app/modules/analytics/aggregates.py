from bisect import bisect_right
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from app.core.constants import ZERO_AMOUNT
from app.core.enums import Currency
from app.modules.analytics.period import AnalyticsPeriod
from app.modules.pricing import CurrencyRateTable, convert_for_report
from app.modules.subscriptions import LiveSubscriptionDto

Granularity = Literal["day", "week", "month"]


def report_amount(amount: Decimal, currency: Currency, rates: CurrencyRateTable) -> Decimal:
    return convert_for_report(amount, currency, rates.anchor, rates)


def monthly_value(row: LiveSubscriptionDto, rates: CurrencyRateTable) -> Decimal:
    """A subscription's price spread over 30 days, in the report currency: its share of MRR."""
    if row.duration_days <= 0:
        return ZERO_AMOUNT
    return report_amount(row.price_paid / row.duration_days * 30, row.currency, rates)


def median(values: list[Decimal]) -> Decimal:
    if not values:
        return ZERO_AMOUNT
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def bucket_starts(period: AnalyticsPeriod, granularity: Granularity) -> list[datetime]:
    starts: list[datetime] = []
    cursor = period.start
    while cursor < period.end:
        starts.append(cursor)
        if granularity == "day":
            cursor += timedelta(days=1)
        elif granularity == "week":
            cursor += timedelta(days=7)
        else:
            year, month = (
                (cursor.year + 1, 1) if cursor.month == 12 else (cursor.year, cursor.month + 1)
            )
            cursor = cursor.replace(
                year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
            )
    return starts


def bucket_index(starts: list[datetime], moment: datetime) -> int:
    return bisect_right(starts, moment) - 1
