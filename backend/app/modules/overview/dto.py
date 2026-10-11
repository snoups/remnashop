from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Optional

from app.core.dto import BaseDto
from app.core.enums import Currency, PaymentGatewayType, PurchaseType

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
    paid_active: int
    trials: int


class RevenueTodayDto(BaseDto):
    report_currency: Currency
    today: Decimal
    yesterday_same_time: Decimal
    change: Optional[float] = None


class RecentPaymentDto(BaseDto):
    user_id: int
    name: str
    username: Optional[str] = None
    plan_name: str
    gateway_type: PaymentGatewayType
    purchase_type: PurchaseType
    amount: Decimal
    currency: Currency
    paid_at: datetime


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


class HostStatsDto(BaseDto):
    cpu_percent: Optional[float] = None
    cpu_count: int
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    disk_total_bytes: Optional[int] = None
    disk_used_bytes: Optional[int] = None


class OverviewDto(BaseDto):
    users: Optional[OverviewUsersDto] = None
    subscriptions: Optional[OverviewSubscriptionsDto] = None
    runtime: list[RuntimeProcessDto]
    host_memory: Optional[HostMemoryDto] = None
    host: Optional[HostStatsDto] = None
    revenue_today: Optional[RevenueTodayDto] = None
    recent_payments: Optional[list[RecentPaymentDto]] = None


class RevenueChartDto(BaseDto):
    days: int
    granularity: Granularity
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily: list[DailyAmountDto]


class OnlineChartDto(BaseDto):
    days: int
    granularity: Granularity
    current: int
    daily_peak: list[DailyCountDto]


class HourlyOnlinePointDto(BaseDto):
    hour: datetime
    peak: Optional[int] = None


class HourlyOnlineDto(BaseDto):
    current: int
    points: list[HourlyOnlinePointDto]


class NodeCardDto(BaseDto):
    name: str
    country_code: str
    is_connected: bool
    is_disabled: bool
    users_online: int
    traffic_used_bytes: Optional[int] = None
    last_status_change: Optional[datetime] = None


class CountryCardDto(BaseDto):
    country_code: str
    nodes: int
    connected: int
    users_online: int


class NodesOverviewDto(BaseDto):
    available: bool
    nodes: list[NodeCardDto]
    countries: list[CountryCardDto]


class AppCountDto(BaseDto):
    app: str
    count: int


class PlatformAppsDto(BaseDto):
    platform: str
    total: int
    apps: list[AppCountDto]


class ClientAppsDto(BaseDto):
    available: bool
    total_devices: int
    average_per_user: float
    platforms: list[PlatformAppsDto]


class AttentionKind(StrEnum):
    NODE_OFFLINE = "node_offline"
    GATEWAY_FAILURES = "gateway_failures"
    BACKUP_FAILED = "backup_failed"
    PAID_NOT_FULFILLED = "paid_not_fulfilled"
    STALE_PENDING = "stale_pending"
    EXPIRING_PAID = "expiring_paid"
    BOT_WEBHOOK = "bot_webhook"


class AttentionItemDto(BaseDto):
    kind: AttentionKind
    severity: Literal["critical", "warning"]
    count: int
    subject: Optional[str] = None
    since: Optional[datetime] = None


class AttentionDto(BaseDto):
    items: list[AttentionItemDto]
