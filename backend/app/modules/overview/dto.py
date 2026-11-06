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
    count: int


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
    plan_name: str
    gateway_type: PaymentGatewayType
    purchase_type: PurchaseType
    amount: Decimal
    currency: Currency
    paid_at: datetime


@dataclass(frozen=True, kw_only=True)
class RuntimeProcessDto:
    process: str
    instance: Optional[str] = None
    # all None: no heartbeat, the process isn't answering
    pid: Optional[int] = None
    uptime_seconds: Optional[float] = None
    rss_bytes: Optional[int] = None
    event_loop_delay_ms: Optional[float] = None
    event_loop_p99_ms: Optional[float] = None


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
class RecapDto:
    report_currency: Currency
    revenue_total: Decimal
    customers: int
    payers: int
    active_subscriptions: int
    transactions: int
    month_revenue: Decimal
    new_customers: int
    new_payers: int
    # None: the panel didn't answer
    nodes: Optional[int]
    countries: Optional[int]
    since: date


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
    PROCESS_DOWN = "process_down"
    OUTBOX_STUCK = "outbox_stuck"
    PANEL_UNAVAILABLE = "panel_unavailable"
    NODE_OFFLINE = "node_offline"
    GATEWAY_FAILURES = "gateway_failures"
    SMTP_FAILED = "smtp_failed"
    BACKUP_FAILED = "backup_failed"
    BACKUP_OVERDUE = "backup_overdue"
    BROADCAST_FAILED = "broadcast_failed"
    PAID_NOT_FULFILLED = "paid_not_fulfilled"
    STALE_PENDING = "stale_pending"
    BROADCAST_STALLED = "broadcast_stalled"
    EMAIL_UNDELIVERABLE = "email_undeliverable"
    EXPIRING_PAID = "expiring_paid"
    API_TOKEN_EXPIRING = "api_token_expiring"
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
