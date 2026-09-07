from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from app.core.dto import BaseDto
from app.core.enums import Currency

# 0 means "all time" -- resolved to a since-date at the first registration.
OverviewDays = Literal[0, 7, 30, 90]
Granularity = Literal["day", "month"]


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
    total: int
    active: int
    limited: int
    expired: int
    disabled: int
    expiring_soon: int


class OverviewPaymentsDto(BaseDto):
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily_revenue: list[DailyAmountDto]


class RuntimeProcessDto(BaseDto):
    process: str
    pid: int
    uptime_seconds: float
    rss_bytes: int
    event_loop_delay_ms: float
    event_loop_p99_ms: float


class HostMemoryDto(BaseDto):
    total_bytes: int
    used_bytes: int


class OverviewOnlineDto(BaseDto):
    current: int
    daily_peak: list[DailyCountDto]


class OverviewDto(BaseDto):
    days: int
    granularity: Granularity
    users: Optional[OverviewUsersDto] = None
    subscriptions: Optional[OverviewSubscriptionsDto] = None
    payments: Optional[OverviewPaymentsDto] = None
    runtime: list[RuntimeProcessDto]
    host_memory: Optional[HostMemoryDto] = None
    online: OverviewOnlineDto
