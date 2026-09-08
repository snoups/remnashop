from decimal import Decimal

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
