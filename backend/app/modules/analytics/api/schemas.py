from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.core.enums import Currency


class AnalyticsKpiResponse(BaseModel):
    total_revenue_by_currency: dict[Currency, Decimal]
    report_currency: Currency
    mrr: Decimal
    arpu: Decimal
    active_subscriptions: int
    paid_orders_count: int
    registered_in_period: int
    paid_in_period: int
    conversion_rate: float


class ChurnSnapshotResponse(BaseModel):
    window_days: int
    prev_active: int
    still_active: int
    churned: int
    churn_rate: float
    retention_rate: float


class AnalyticsResponse(BaseModel):
    days: int
    kpi: AnalyticsKpiResponse
    churn: ChurnSnapshotResponse


class FunnelStepResponse(BaseModel):
    key: str
    count: int
    pct_of_start: float
    pct_of_prev: float


class FunnelResponse(BaseModel):
    days: int
    steps: list[FunnelStepResponse]


class CohortRowResponse(BaseModel):
    cohort: str
    cohort_size: int
    retention_by_month: list[float]


class CohortsResponse(BaseModel):
    cohorts: list[CohortRowResponse]


class LtvBucketResponse(BaseModel):
    label: str
    lower_bound: Decimal
    upper_bound: Optional[Decimal]
    users: int


class LtvDistributionResponse(BaseModel):
    report_currency: Currency
    buckets: list[LtvBucketResponse]
