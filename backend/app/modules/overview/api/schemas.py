from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.core.enums import Currency


class DailyCountResponse(BaseModel):
    day: date
    count: int


class DailyAmountResponse(BaseModel):
    day: date
    amount: Decimal


class OverviewUsersResponse(BaseModel):
    total: int
    new_today: int
    daily_registrations: list[DailyCountResponse]


class OverviewSubscriptionsResponse(BaseModel):
    active: int


class OverviewPaymentsResponse(BaseModel):
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily_revenue: list[DailyAmountResponse]


class OverviewResponse(BaseModel):
    days: int
    users: Optional[OverviewUsersResponse] = None
    subscriptions: Optional[OverviewSubscriptionsResponse] = None
    payments: Optional[OverviewPaymentsResponse] = None
