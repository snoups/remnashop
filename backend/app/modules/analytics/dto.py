from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.core.enums import Currency, PaymentGatewayType, PromocodeRewardType, PromocodeStatus
from app.modules.analytics.aggregates import Granularity
from app.modules.analytics.sources import SourceKind


class AnalyticsPeriodInfoDto(BaseModel):
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime


class PeriodKpiDto(BaseModel):
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


class SnapshotKpiDto(BaseModel):
    mrr: Decimal
    paid_subscriptions: int
    limited_subscriptions: int
    active_trials: int
    paying_customers: int
    never_connected: int
    expiring_soon_days: int
    expiring_soon: int
    expiring_soon_mrr: Decimal
    trials_ending_days: int
    trials_ending_soon: int
    points_owed: Decimal
    bonus_days_owed: int


class AnalyticsDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    revenue_by_currency: dict[Currency, Decimal]
    conversion_window_days: int
    current: PeriodKpiDto
    previous: PeriodKpiDto
    snapshot: SnapshotKpiDto


class FunnelStepDto(BaseModel):
    key: str
    count: int
    pct_of_start: float
    pct_of_prev: float


class FunnelSourceRowDto(BaseModel):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registered: int
    connected: int
    paid: int
    repeat_paid: int


class FunnelDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    steps: list[FunnelStepDto]
    paid_via_trial: int
    # None: nobody registered in the previous period
    previous_conversion: Optional[float]
    by_source: list[FunnelSourceRowDto]


class CohortRowDto(BaseModel):
    cohort: str
    cohort_size: int
    retention_by_month: list[float]


class CohortsDto(BaseModel):
    cohorts: list[CohortRowDto]


class LtvBucketDto(BaseModel):
    label: str
    lower_bound: Decimal
    upper_bound: Optional[Decimal]
    users: int


class LtvDistributionDto(BaseModel):
    report_currency: Currency
    buckets: list[LtvBucketDto]
    payers: int
    mean: Decimal
    median: Decimal


class LtvGroupDto(BaseModel):
    key: str
    source: Optional[SourceKind]
    customers: int
    avg_ltv: Decimal


class TopPayerDto(BaseModel):
    user_id: int
    name: str
    username: Optional[str]
    # live paid subscriptions' plans, the one expiring last first
    current_plans: list[str]
    payments: int
    spent: Decimal
    last_paid_at: datetime


class LtvBreakdownDto(BaseModel):
    report_currency: Currency
    by_first_plan: list[LtvGroupDto]
    by_source: list[LtvGroupDto]
    top_payers: list[TopPayerDto]


class SourceRowDto(BaseModel):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registrations: int
    payers: int
    conversion_rate: float
    revenue: Decimal
    revenue_per_payer: Decimal


class ReferralPaybackDto(BaseModel):
    referred_revenue: Decimal
    reward_days: int
    reward_points: int
    referrers: int
    deep_levels_revenue_share: float


class TopReferrerDto(BaseModel):
    user_id: int
    name: str
    invited: int
    paid: int
    revenue: Decimal
    reward_days: int


class ChannelRevenueDto(BaseModel):
    source: SourceKind
    revenue: Decimal


class SourcesDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    channels: list[SourceRowDto]
    previous_channels: list[ChannelRevenueDto]
    ad_links: list[SourceRowDto]
    referral: ReferralPaybackDto
    top_referrers: list[TopReferrerDto]


class RevenueTotalsDto(BaseModel):
    revenue: Decimal
    payments: int
    avg_check: Decimal
    median_check: Decimal
    refunds: int
    refunded: Decimal
    previous_revenue: Decimal
    previous_payments: int
    previous_refunds: int


class RevenueBucketDto(BaseModel):
    start: datetime
    new: Decimal
    renew: Decimal
    change: Decimal
    previous_total: Decimal


class RevenueGroupDto(BaseModel):
    key: str
    payments: int
    revenue: Decimal


class GatewayStatsDto(BaseModel):
    gateway_type: PaymentGatewayType
    paid: int
    canceled: int
    failed: int
    refunded: int
    revenue: Decimal


class RevenueDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    granularity: str
    totals: RevenueTotalsDto
    series: list[RevenueBucketDto]
    by_plan: list[RevenueGroupDto]
    by_duration: list[RevenueGroupDto]
    by_channel: list[RevenueGroupDto]
    gateways: list[GatewayStatsDto]


class TrialDayBucketDto(BaseModel):
    key: str
    count: int


class TimeToPayBucketDto(BaseModel):
    key: str
    via_trial: int
    direct: int


class TrialDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    trials: int
    converted: int
    conversion_rate: float
    # None: nobody took a trial in the previous period, nothing to compare with
    previous_conversion_rate: Optional[float]
    previous_trials: int
    revenue_from_converted: Decimal
    previous_revenue_from_converted: Decimal
    median_days_to_pay: int
    trial_days: int
    by_trial_day: list[TrialDayBucketDto]
    time_to_first_payment: list[TimeToPayBucketDto]
    plans_after_trial: list[RevenueGroupDto]


class RetentionPointDto(BaseModel):
    months: int
    rate: float
    eligible: int


class ExpiringWeekDto(BaseModel):
    key: str
    count: int
    mrr_at_risk: Decimal


class ExpiringCustomerDto(BaseModel):
    user_id: int
    name: str
    username: Optional[str]
    # plans of the customer's subscriptions expiring in the window, the nearest first
    plan_names: list[str]
    expire_at: datetime
    spent: Decimal
    renewals: int


class ExpiringCustomerPageDto(BaseModel):
    items: list[ExpiringCustomerDto]
    total: int


@dataclass(frozen=True, kw_only=True)
class ListExpiringCustomersDto:
    page: int
    page_size: int


class PlanActiveDto(BaseModel):
    plan_name: str
    active: int
    limited: int


class MonthlyChurnDto(BaseModel):
    month: str
    base: int
    churned: int
    rate: float


class RetentionDto(BaseModel):
    report_currency: Currency
    points: list[RetentionPointDto]
    avg_paid_months: float
    expiring_paid: int
    expiring_trials: int
    expiring_weeks: list[ExpiringWeekDto]
    active_by_plan: list[PlanActiveDto]
    monthly_churn: list[MonthlyChurnDto]


@dataclass(frozen=True, kw_only=True)
class AnalyticsPeriodQueryDto:
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class GetRevenueDto(AnalyticsPeriodQueryDto):
    granularity: Granularity = "day"


class RewardTypeCountDto(BaseModel):
    reward_type: PromocodeRewardType
    activations: int


class PromocodeRowDto(BaseModel):
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


class PromocodeStatsDto(BaseModel):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    activations: int
    codes_used: int
    discount_given: Decimal
    revenue_with_discount: Decimal
    revenue_share: float
    free_rewards: int
    free_reward_conversion: float
    previous_activations: int
    previous_discount_given: Decimal
    previous_revenue_with_discount: Decimal
    # None: no free reward was activated in the previous period
    previous_free_reward_conversion: Optional[float]
    by_reward_type: list[RewardTypeCountDto]
    codes: list[PromocodeRowDto]
