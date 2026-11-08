from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum
from typing import Literal, Optional

from pydantic import BaseModel, computed_field

from app.core.enums import Currency, PaymentGatewayType, PurchaseType
from app.modules.overview.dto import AttentionKind


class DailyCountResponse(BaseModel):
    day: date
    count: int


class DailyAmountResponse(BaseModel):
    day: date
    amount: Decimal
    count: int


class OverviewUsersResponse(BaseModel):
    total: int
    new_today: int


class OverviewSubscriptionsResponse(BaseModel):
    total: int
    active: int
    limited: int
    expired: int
    disabled: int
    expiring_soon: int
    paid_active: int
    trials: int


class RevenueTodayResponse(BaseModel):
    report_currency: Currency
    today: Decimal
    yesterday_same_time: Decimal
    change: Optional[float] = None


class RecentPaymentResponse(BaseModel):
    transaction_id: int
    user_id: int
    name: str
    plan_name: str
    duration_days: int
    gateway_type: PaymentGatewayType
    purchase_type: PurchaseType
    amount: Decimal
    currency: Currency
    paid_at: datetime


class RuntimeProcessResponse(BaseModel):
    process: str
    instance: Optional[str]
    pid: Optional[int]
    uptime_seconds: Optional[float]
    rss_bytes: Optional[int]
    event_loop_delay_ms: Optional[float]
    event_loop_p99_ms: Optional[float]


class HostMemoryResponse(BaseModel):
    total_bytes: int
    used_bytes: int


class HostStatsResponse(BaseModel):
    cpu_percent: Optional[float] = None
    cpu_count: int
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    disk_total_bytes: Optional[int] = None
    disk_used_bytes: Optional[int] = None


class OverviewResponse(BaseModel):
    users: Optional[OverviewUsersResponse] = None
    subscriptions: Optional[OverviewSubscriptionsResponse] = None
    runtime: list[RuntimeProcessResponse]
    host_memory: Optional[HostMemoryResponse] = None
    host: Optional[HostStatsResponse] = None
    revenue_today: Optional[RevenueTodayResponse] = None
    recent_payments: Optional[list[RecentPaymentResponse]] = None


class RecapResponse(BaseModel):
    report_currency: Currency
    revenue_total: Decimal
    customers: int
    payers: int
    active_subscriptions: int
    transactions: int
    month_revenue: Decimal
    new_customers: int
    new_payers: int
    nodes: Optional[int] = None
    countries: Optional[int] = None
    since: date


class RevenueChartResponse(BaseModel):
    days: int
    granularity: Literal["day", "month"]
    paid_orders_count: int
    report_currency: Currency
    daily: list[DailyAmountResponse]


class OnlineChartResponse(BaseModel):
    days: int
    granularity: Literal["day", "month"]
    current: int
    daily_peak: list[DailyCountResponse]


class HourlyOnlinePointResponse(BaseModel):
    hour: datetime
    peak: Optional[int]


class HourlyOnlineResponse(BaseModel):
    current: int
    points: list[HourlyOnlinePointResponse]


class NodeCardResponse(BaseModel):
    name: str
    country_code: str
    is_connected: bool
    is_disabled: bool
    users_online: int
    traffic_used_bytes: Optional[int]
    last_status_change: Optional[datetime]


class CountryCardResponse(BaseModel):
    country_code: str
    nodes: int
    connected: int
    users_online: int


class NodesOverviewResponse(BaseModel):
    available: bool
    nodes: list[NodeCardResponse]
    countries: list[CountryCardResponse]


class AppCountResponse(BaseModel):
    app: str
    count: int


class PlatformAppsResponse(BaseModel):
    platform: str
    total: int
    apps: list[AppCountResponse]


class ClientAppsResponse(BaseModel):
    available: bool
    total_devices: int
    average_per_user: float
    platforms: list[PlatformAppsResponse]


class AttentionItemResponse(BaseModel):
    kind: AttentionKind
    severity: Literal["critical", "warning"]
    count: int
    subject: Optional[str]
    since: Optional[datetime]


class AttentionResponse(BaseModel):
    items: list[AttentionItemResponse]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return len(self.items)


class OverviewPeriodDays(IntEnum):
    # a query string isn't coerced into Literal[7, 30, 90] (`?days=7` 422s), an
    # IntEnum is; mapped back to OverviewDays when building GetOverviewChartDto
    ALL = 0
    SEVEN = 7
    THIRTY = 30
    NINETY = 90
