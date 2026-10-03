from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from app.core.dto import BaseDto
from app.core.enums import Currency

# 0 means "all time", resolved to the first registration
OverviewDays = Literal[0, 7, 30, 90]
Granularity = Literal["day", "month"]


@dataclass(frozen=True, kw_only=True)
class GetOverviewChartDto:
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


class OverviewSubscriptionsDto(BaseDto):
    total: int
    active: int
    limited: int
    expired: int
    disabled: int
    expiring_soon: int


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


class OverviewDto(BaseDto):
    users: Optional[OverviewUsersDto] = None
    subscriptions: Optional[OverviewSubscriptionsDto] = None
    runtime: list[RuntimeProcessDto]
    host_memory: Optional[HostMemoryDto] = None


class RevenueChartDto(BaseDto):
    days: int
    granularity: Granularity
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily: list[DailyAmountDto]


class RegistrationsChartDto(BaseDto):
    days: int
    granularity: Granularity
    daily: list[DailyCountDto]


class OnlineChartDto(BaseDto):
    days: int
    granularity: Granularity
    current: int
    daily_peak: list[DailyCountDto]
