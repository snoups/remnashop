from datetime import date
from decimal import Decimal
from typing import Literal, Optional

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
    total: int
    active: int
    limited: int
    expired: int
    expiring_soon: int


class OverviewPaymentsResponse(BaseModel):
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily_revenue: list[DailyAmountResponse]


class RuntimeProcessResponse(BaseModel):
    process: str
    pid: int
    uptime_seconds: float
    rss_bytes: int
    event_loop_delay_ms: float
    event_loop_p99_ms: float


class HostMemoryResponse(BaseModel):
    total_bytes: int
    used_bytes: int


class OverviewOnlineResponse(BaseModel):
    current: int
    daily_peak: list[DailyCountResponse]


class OverviewResponse(BaseModel):
    days: int
    granularity: Literal["day", "month"]
    users: Optional[OverviewUsersResponse] = None
    subscriptions: Optional[OverviewSubscriptionsResponse] = None
    payments: Optional[OverviewPaymentsResponse] = None
    runtime: list[RuntimeProcessResponse]
    host_memory: Optional[HostMemoryResponse] = None
    online: OverviewOnlineResponse
