from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Optional

from app.core.enums import Currency, PaymentGatewayType, PurchaseType

# 0 means "all time", resolved to the first registration
OverviewDays = Literal[0, 7, 30, 90]
Granularity = Literal["day", "month"]


@dataclass(frozen=True, kw_only=True)
class GetOverviewChartDto:
    days: OverviewDays = 7


@dataclass(frozen=True, kw_only=True)
class DailyCountDto:
    day: date
    count: int


@dataclass(frozen=True, kw_only=True)
class DailyAmountDto:
    day: date
    amount: Decimal


@dataclass(frozen=True, kw_only=True)
class OverviewUsersDto:
    total: int
    new_today: int


@dataclass(frozen=True, kw_only=True)
class OverviewSubscriptionsDto:
    total: int
    active: int
    limited: int
    expired: int
    disabled: int
    expiring_soon: int
    paid_active: int
    trials: int


@dataclass(frozen=True, kw_only=True)
class RevenueTodayDto:
    report_currency: Currency
    today: Decimal
    yesterday_same_time: Decimal
    change: Optional[float] = None


@dataclass(frozen=True, kw_only=True)
class RecentPaymentDto:
    user_id: int
    name: str
    username: Optional[str] = None
    plan_name: str
    gateway_type: PaymentGatewayType
    purchase_type: PurchaseType
    amount: Decimal
    currency: Currency
    paid_at: datetime


@dataclass(frozen=True, kw_only=True)
class RuntimeProcessDto:
    process: str
    pid: int
    uptime_seconds: float
    rss_bytes: int
    event_loop_delay_ms: float
    event_loop_p99_ms: float


@dataclass(frozen=True, kw_only=True)
class HostMemoryDto:
    total_bytes: int
    used_bytes: int


@dataclass(frozen=True, kw_only=True)
class HostStatsDto:
    cpu_percent: Optional[float] = None
    cpu_count: int
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    disk_total_bytes: Optional[int] = None
    disk_used_bytes: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class OverviewDto:
    users: Optional[OverviewUsersDto] = None
    subscriptions: Optional[OverviewSubscriptionsDto] = None
    runtime: list[RuntimeProcessDto]
    host_memory: Optional[HostMemoryDto] = None
    host: Optional[HostStatsDto] = None
    revenue_today: Optional[RevenueTodayDto] = None
    recent_payments: Optional[list[RecentPaymentDto]] = None


@dataclass(frozen=True, kw_only=True)
class RevenueChartDto:
    days: int
    granularity: Granularity
    paid_orders_count: int
    revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    daily: list[DailyAmountDto]


@dataclass(frozen=True, kw_only=True)
class OnlineChartDto:
    days: int
    granularity: Granularity
    current: int
    daily_peak: list[DailyCountDto]


@dataclass(frozen=True, kw_only=True)
class HourlyOnlinePointDto:
    hour: datetime
    peak: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class HourlyOnlineDto:
    current: int
    points: list[HourlyOnlinePointDto]


@dataclass(frozen=True, kw_only=True)
class NodeCardDto:
    name: str
    country_code: str
    is_connected: bool
    is_disabled: bool
    users_online: int
    traffic_used_bytes: Optional[int] = None
    last_status_change: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class CountryCardDto:
    country_code: str
    nodes: int
    connected: int
    users_online: int


@dataclass(frozen=True, kw_only=True)
class NodesOverviewDto:
    available: bool
    nodes: list[NodeCardDto]
    countries: list[CountryCardDto]


@dataclass(frozen=True, kw_only=True)
class AppCountDto:
    app: str
    count: int


@dataclass(frozen=True, kw_only=True)
class PlatformAppsDto:
    platform: str
    total: int
    apps: list[AppCountDto]


@dataclass(frozen=True, kw_only=True)
class ClientAppsDto:
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


@dataclass(frozen=True, kw_only=True)
class AttentionItemDto:
    kind: AttentionKind
    severity: Literal["critical", "warning"]
    count: int
    subject: Optional[str] = None
    since: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class AttentionDto:
    items: list[AttentionItemDto]
