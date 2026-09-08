from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional

from app.core.dto import BaseDto
from app.core.enums import Currency

# 0 means "all time" -- resolved to a since-date at the first registration,
# same convention as overview/dto.py's OverviewDays.
AnalyticsDays = Literal[0, 7, 30, 90]


@dataclass(frozen=True, kw_only=True)
class GetAnalyticsDto:
    days: AnalyticsDays = 7


class AnalyticsKpiDto(BaseDto):
    total_revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    mrr: Decimal
    arpu: Decimal
    active_subscriptions: int
    paid_orders_count: int
    registered_in_period: int
    paid_in_period: int
    conversion_rate: float


class ChurnSnapshotDto(BaseDto):
    window_days: int
    prev_active: int
    still_active: int
    churned: int
    churn_rate: float
    retention_rate: float


class AnalyticsDto(BaseDto):
    days: int
    kpi: AnalyticsKpiDto
    churn: ChurnSnapshotDto


class FunnelStepDto(BaseDto):
    key: str
    count: int
    pct_of_start: float
    pct_of_prev: float


class FunnelDto(BaseDto):
    days: int
    steps: list[FunnelStepDto]


@dataclass(frozen=True, kw_only=True)
class GetFunnelDto:
    days: AnalyticsDays = 7


class CohortRowDto(BaseDto):
    cohort: str
    cohort_size: int
    retention_by_month: list[float]


class CohortsDto(BaseDto):
    cohorts: list[CohortRowDto]


class LtvBucketDto(BaseDto):
    label: str
    lower_bound: Decimal
    upper_bound: Optional[Decimal]
    users: int


class LtvDistributionDto(BaseDto):
    report_currency: Currency
    buckets: list[LtvBucketDto]
