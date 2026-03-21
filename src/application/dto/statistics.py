from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.core.enums import PaymentGatewayType


@dataclass(frozen=True)
class UserPaymentStatsDto:
    currency: str
    total_amount: float


@dataclass(frozen=True)
class UserStatisticsDto:
    last_payment_at: Optional[datetime]
    payment_amounts: list[UserPaymentStatsDto]
    registered_at: datetime
    referrer_telegram_id: Optional[int]
    referrer_username: Optional[str]
    referrals_level_1: int
    referrals_level_2: int
    reward_points: int
    reward_days: int


@dataclass
class ReferralStatisticsDto:
    total_referrals: int
    level_1_count: int
    level_2_count: int
    unique_referrers: int
    total_rewards_issued: int
    total_points_issued: int
    total_days_issued: int
    top_referrer_referrals_count: int
    top_referrer_username: Optional[str] = None
    top_referrer_telegram_id: Optional[int] = None


@dataclass(frozen=True)
class SubscriptionStatsDto:
    total: int
    total_active: int
    total_expired: int
    active_trial: int
    expiring_soon: int
    total_unlimited: int
    total_traffic: int
    total_devices: int


@dataclass(frozen=True)
class PlanSubStatsDto:
    plan_id: int
    plan_name: str
    total_subs: int
    active_subs: int
    expired_subs: int
    expiring_soon: int
    total_unlimited: int
    total_traffic: int
    total_devices: int
    popular_duration: int


@dataclass(frozen=True)
class PlanIncomeDto:
    plan_id: int
    currency: str
    total_income: float


@dataclass(frozen=True)
class GatewayStatsDto:
    gateway_type: PaymentGatewayType
    total_income: Decimal
    daily_income: Decimal
    weekly_income: Decimal
    monthly_income: Decimal
    paid_count: int
    total_discounts: Decimal
    total_transactions: int
    completed_transactions: int
    free_transactions: int
