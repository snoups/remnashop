from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel

from app.core.enums import Currency, PaymentGatewayType, PromocodeRewardType, PromocodeStatus
from app.modules.analytics.sources import SourceKind


class AnalyticsPeriodInfoResponse(BaseModel):
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime


class PeriodKpiResponse(BaseModel):
    revenue: Decimal
    payments: int
    paying_users: int
    arppu: Decimal
    new_payers: int
    conversion_cohort: int
    converted: int
    conversion_rate: float
    churn_base: int
    churned: int
    churn_rate: float


class SnapshotKpiResponse(BaseModel):
    mrr: Decimal
    paid_subscriptions: int
    limited_subscriptions: int
    active_trials: int


class AnalyticsResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    report_currency: Currency
    revenue_by_currency: dict[Currency, Decimal]
    conversion_window_days: int
    current: PeriodKpiResponse
    previous: PeriodKpiResponse
    snapshot: SnapshotKpiResponse


class FunnelStepResponse(BaseModel):
    key: str
    count: int
    pct_of_start: float
    pct_of_prev: float


class FunnelSourceRowResponse(BaseModel):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registered: int
    connected: int
    paid: int
    repeat_paid: int


class FunnelResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    steps: list[FunnelStepResponse]
    paid_via_trial: int
    by_source: list[FunnelSourceRowResponse]


class CohortRowResponse(BaseModel):
    cohort: str
    cohort_size: int
    retention_by_month: list[float]


class CohortsResponse(BaseModel):
    items: list[CohortRowResponse]
    total: int


class LtvBucketResponse(BaseModel):
    label: str
    lower_bound: Decimal
    upper_bound: Optional[Decimal]
    users: int


class LtvDistributionResponse(BaseModel):
    report_currency: Currency
    buckets: list[LtvBucketResponse]
    payers: int
    mean: Decimal
    median: Decimal


class LtvGroupResponse(BaseModel):
    key: str
    source: Optional[SourceKind]
    customers: int
    avg_ltv: Decimal


class TopPayerResponse(BaseModel):
    user_id: int
    name: str
    username: Optional[str]
    current_plan: Optional[str]
    payments: int
    spent: Decimal
    last_paid_at: datetime


class LtvBreakdownResponse(BaseModel):
    report_currency: Currency
    by_first_plan: list[LtvGroupResponse]
    by_source: list[LtvGroupResponse]
    top_payers: list[TopPayerResponse]


class RevenueTotalsResponse(BaseModel):
    revenue: Decimal
    payments: int
    avg_check: Decimal
    median_check: Decimal
    refunds: int
    refunded: Decimal
    previous_revenue: Decimal
    previous_payments: int


class RevenueBucketResponse(BaseModel):
    start: datetime
    new: Decimal
    renew: Decimal
    change: Decimal
    previous_total: Decimal


class RevenueGroupResponse(BaseModel):
    key: str
    payments: int
    revenue: Decimal


class GatewayStatsResponse(BaseModel):
    gateway_type: PaymentGatewayType
    paid: int
    canceled: int
    failed: int
    refunded: int
    revenue: Decimal


class RevenueResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    report_currency: Currency
    granularity: Literal["day", "week", "month"]
    totals: RevenueTotalsResponse
    series: list[RevenueBucketResponse]
    by_plan: list[RevenueGroupResponse]
    by_duration: list[RevenueGroupResponse]
    by_channel: list[RevenueGroupResponse]
    gateways: list[GatewayStatsResponse]


class TrialDayBucketResponse(BaseModel):
    key: str
    count: int


class TimeToPayBucketResponse(BaseModel):
    key: str
    via_trial: int
    direct: int


class TrialResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    report_currency: Currency
    trials: int
    converted: int
    conversion_rate: float
    previous_conversion_rate: float
    revenue_from_converted: Decimal
    median_days_to_pay: int
    trial_days: int
    by_trial_day: list[TrialDayBucketResponse]
    time_to_first_payment: list[TimeToPayBucketResponse]
    plans_after_trial: list[RevenueGroupResponse]


class RetentionPointResponse(BaseModel):
    months: int
    rate: float
    eligible: int


class ExpiringWeekResponse(BaseModel):
    key: str
    count: int
    mrr_at_risk: Decimal


class ExpiringCustomerResponse(BaseModel):
    user_id: int
    name: str
    username: Optional[str]
    plan_name: str
    expire_at: datetime
    spent: Decimal
    renewals: int


class PlanActiveResponse(BaseModel):
    plan_name: str
    active: int
    limited: int


class MonthlyChurnResponse(BaseModel):
    month: str
    base: int
    churned: int
    rate: float


class RetentionResponse(BaseModel):
    report_currency: Currency
    points: list[RetentionPointResponse]
    avg_paid_months: float
    expiring_paid: int
    expiring_trials: int
    expiring_weeks: list[ExpiringWeekResponse]
    expiring_top: list[ExpiringCustomerResponse]
    active_by_plan: list[PlanActiveResponse]
    monthly_churn: list[MonthlyChurnResponse]


class SourceRowResponse(BaseModel):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registrations: int
    payers: int
    conversion_rate: float
    revenue: Decimal
    revenue_per_payer: Decimal


class ReferralPaybackResponse(BaseModel):
    referred_revenue: Decimal
    reward_days: int
    reward_points: int
    referrers: int
    deep_levels_revenue_share: float


class TopReferrerResponse(BaseModel):
    user_id: int
    name: str
    invited: int
    paid: int
    revenue: Decimal
    reward_days: int


class SourcesResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    report_currency: Currency
    channels: list[SourceRowResponse]
    ad_links: list[SourceRowResponse]
    referral: ReferralPaybackResponse
    top_referrers: list[TopReferrerResponse]


class RewardTypeCountResponse(BaseModel):
    reward_type: PromocodeRewardType
    activations: int


class PromocodeRowResponse(BaseModel):
    promocode_id: int
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int]
    reward_duration_days: Optional[int]
    activations: int
    total_activations: int
    max_activations: Optional[int]
    revenue_after: Decimal
    conversion_rate: Optional[float]
    status: PromocodeStatus


class PromocodeStatsResponse(BaseModel):
    period: AnalyticsPeriodInfoResponse
    report_currency: Currency
    activations: int
    codes_used: int
    discount_given: Decimal
    revenue_with_discount: Decimal
    revenue_share: float
    free_reward_conversion: float
    by_reward_type: list[RewardTypeCountResponse]
    codes: list[PromocodeRowResponse]
