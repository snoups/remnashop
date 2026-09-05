from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from app.core.dto import BaseDto
from app.core.enums import Currency

OverviewDays = Literal[7, 30, 90]


@dataclass(frozen=True, kw_only=True)
class GetOverviewDto:
    days: OverviewDays = 7


class DailyCountDto(BaseDto):
    day: date
    count: int


class DailyAmountDto(BaseDto):
    day: date
    amount: Decimal


class OverviewUsersDto(BaseDto):
    total: int
    new_today: int
    daily_registrations: list[DailyCountDto]


class OverviewSubscriptionsDto(BaseDto):
    active: int


class OverviewPaymentsDto(BaseDto):
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily_revenue: list[DailyAmountDto]


class OverviewDto(BaseDto):
    days: int
    users: Optional[OverviewUsersDto] = None
    subscriptions: Optional[OverviewSubscriptionsDto] = None
    payments: Optional[OverviewPaymentsDto] = None
