from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.core.dto import BaseDto
from app.core.enums import Currency, PaymentGatewayType, PromocodeRewardType, PromocodeStatus
from app.modules.analytics.aggregates import Granularity
from app.modules.analytics.sources import SourceKind


class AnalyticsPeriodInfoDto(BaseDto):
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime


class PeriodKpiDto(BaseDto):
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


class SnapshotKpiDto(BaseDto):
    mrr: Decimal
    paid_subscriptions: int
    limited_subscriptions: int
    active_trials: int


class AnalyticsDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    revenue_by_currency: dict[Currency, Decimal]
    conversion_window_days: int
    current: PeriodKpiDto
    previous: PeriodKpiDto
    snapshot: SnapshotKpiDto


class FunnelStepDto(BaseDto):
    key: str
    count: int
    pct_of_start: float
    pct_of_prev: float


class FunnelSourceRowDto(BaseDto):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registered: int
    connected: int
    paid: int
    repeat_paid: int


class FunnelDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    steps: list[FunnelStepDto]
    paid_via_trial: int
    by_source: list[FunnelSourceRowDto]


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
    payers: int
    mean: Decimal
    median: Decimal


class LtvGroupDto(BaseDto):
    key: str
    source: Optional[SourceKind]
    customers: int
    avg_ltv: Decimal


class TopPayerDto(BaseDto):
    user_id: int
    name: str
    username: Optional[str]
    current_plan: Optional[str]
    payments: int
    spent: Decimal
    last_paid_at: datetime


class LtvBreakdownDto(BaseDto):
    report_currency: Currency
    by_first_plan: list[LtvGroupDto]
    by_source: list[LtvGroupDto]
    top_payers: list[TopPayerDto]


class SourceRowDto(BaseDto):
    source: SourceKind
    ad_link_id: Optional[int]
    name: Optional[str]
    registrations: int
    payers: int
    conversion_rate: float
    revenue: Decimal
    revenue_per_payer: Decimal


class ReferralPaybackDto(BaseDto):
    referred_revenue: Decimal
    reward_days: int
    reward_points: int
    referrers: int
    deep_levels_revenue_share: float


class TopReferrerDto(BaseDto):
    user_id: int
    name: str
    invited: int
    paid: int
    revenue: Decimal
    reward_days: int


class SourcesDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    channels: list[SourceRowDto]
    ad_links: list[SourceRowDto]
    referral: ReferralPaybackDto
    top_referrers: list[TopReferrerDto]


class RevenueTotalsDto(BaseDto):
    revenue: Decimal
    payments: int
    avg_check: Decimal
    median_check: Decimal
    refunds: int
    refunded: Decimal
    previous_revenue: Decimal
    previous_payments: int


class RevenueBucketDto(BaseDto):
    start: datetime
    new: Decimal
    renew: Decimal
    change: Decimal
    previous_total: Decimal


class RevenueGroupDto(BaseDto):
    key: str
    payments: int
    revenue: Decimal


class GatewayStatsDto(BaseDto):
    gateway_type: PaymentGatewayType
    paid: int
    canceled: int
    failed: int
    refunded: int
    revenue: Decimal


class RevenueDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    granularity: str
    totals: RevenueTotalsDto
    series: list[RevenueBucketDto]
    by_plan: list[RevenueGroupDto]
    by_duration: list[RevenueGroupDto]
    by_channel: list[RevenueGroupDto]
    gateways: list[GatewayStatsDto]


class TrialDayBucketDto(BaseDto):
    key: str
    count: int


class TimeToPayBucketDto(BaseDto):
    key: str
    via_trial: int
    direct: int


class TrialDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    trials: int
    converted: int
    conversion_rate: float
    previous_conversion_rate: float
    revenue_from_converted: Decimal
    median_days_to_pay: int
    trial_days: int
    by_trial_day: list[TrialDayBucketDto]
    time_to_first_payment: list[TimeToPayBucketDto]
    plans_after_trial: list[RevenueGroupDto]


class RetentionPointDto(BaseDto):
    months: int
    rate: float
    eligible: int


class ExpiringWeekDto(BaseDto):
    key: str
    count: int
    mrr_at_risk: Decimal


class ExpiringCustomerDto(BaseDto):
    user_id: int
    name: str
    username: Optional[str]
    plan_name: str
    expire_at: datetime
    spent: Decimal
    renewals: int


class PlanActiveDto(BaseDto):
    plan_name: str
    active: int
    limited: int


class MonthlyChurnDto(BaseDto):
    month: str
    base: int
    churned: int
    rate: float


class RetentionDto(BaseDto):
    report_currency: Currency
    points: list[RetentionPointDto]
    avg_paid_months: float
    expiring_paid: int
    expiring_trials: int
    expiring_weeks: list[ExpiringWeekDto]
    expiring_top: list[ExpiringCustomerDto]
    active_by_plan: list[PlanActiveDto]
    monthly_churn: list[MonthlyChurnDto]


@dataclass(frozen=True, kw_only=True)
class AnalyticsPeriodQueryDto:
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class GetRevenueDto(AnalyticsPeriodQueryDto):
    granularity: Granularity = "day"


class RewardTypeCountDto(BaseDto):
    reward_type: PromocodeRewardType
    activations: int


class PromocodeRowDto(BaseDto):
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


class PromocodeStatsDto(BaseDto):
    period: AnalyticsPeriodInfoDto
    report_currency: Currency
    activations: int
    codes_used: int
    discount_given: Decimal
    revenue_with_discount: Decimal
    revenue_share: float
    free_reward_conversion: float
    by_reward_type: list[RewardTypeCountDto]
    codes: list[PromocodeRowDto]
