from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    Currency,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from app.modules.users import UserDto

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


class ReferralDto(BaseDto, TimestampMixin):
    referrer_id: Optional[int] = None
    referred_id: int
    level: int


class ReferralRewardDto(BaseDto, TimestampMixin):
    referral_id: Optional[int] = None
    referrer_id: Optional[int] = None
    subscription_id: Optional[int] = None
    type: ReferralRewardType
    amount: Decimal
    # owner of the subscription whose payment earned it; filled by queries only
    buyer_id: Optional[int] = None


class ReferralSettingsDto(BaseDto, TimestampMixin):
    enabled: bool = False
    max_level: int = 1
    accrual_strategy: ReferralAccrualStrategy = ReferralAccrualStrategy.FIRST_PAYMENT
    reward_type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    reward_strategy: ReferralRewardStrategy = ReferralRewardStrategy.AMOUNT
    reward_amounts: dict[int, Decimal] = field(default_factory=dict)
    # EXTRA_DAYS only: no days for someone who never paid for a subscription
    days_require_paid_subscription: bool = True
    # what a user registering through a link gets; 0 = nothing
    invitee_reward_type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    invitee_reward_amount: int = 0
    # not stored here: pricing's anchor, what a PERCENT points reward is counted in
    anchor_currency: Optional[Currency] = None


@dataclass(frozen=True, kw_only=True)
class ReferralRevenueDto:
    # what the user's downline has paid, converted to one report currency
    amount: Decimal
    currency: Currency
    paying_count: int


@dataclass(frozen=True, kw_only=True)
class ReferralStatsRewardDto:
    type: ReferralRewardType
    amount: Decimal
    created_at: Optional[datetime]
    # admin view only: who paid for it and how deep below this user they are
    buyer: Optional[UserDto] = None
    level: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class ReferralStatsDto:
    referral_code: Optional[str]
    referrer_id: Optional[int]
    points: Decimal
    bonus_days: int
    counts_by_level: dict[int, int]
    rewards: list[ReferralStatsRewardDto]
    # admin view only
    referrer: Optional[UserDto] = None


@dataclass(frozen=True, kw_only=True)
class UpdateReferralSettingsDto:
    # None = leave unchanged, matching UpdateUserDto's convention.
    enabled: Optional[bool] = None
    max_level: Optional[int] = None
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
    reward_strategy: Optional[ReferralRewardStrategy] = None
    reward_amounts: Optional[dict[int, Decimal]] = None
    days_require_paid_subscription: Optional[bool] = None
    invitee_reward_type: Optional[ReferralRewardType] = None
    invitee_reward_amount: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class ReferralRewardTotalsDto:
    count: int
    # keyed by type: reward_type can change between payouts
    amounts: dict[ReferralRewardType, Decimal]


@dataclass(frozen=True, kw_only=True)
class ReferralListItemDto:
    referral: ReferralDto
    referred: Optional[UserDto]
    referrer: Optional[UserDto]
    rewards: ReferralRewardTotalsDto


@dataclass(frozen=True, kw_only=True)
class ReferralSummaryDto:
    total_count: int
    referrers_count: int
    rewarded_count: int
    reward_amounts: dict[ReferralRewardType, Decimal]

    @property
    def conversion_rate(self) -> Decimal:
        # share of referrals that earned at least one reward
        return Decimal(self.rewarded_count) / self.total_count if self.total_count else Decimal(0)


@dataclass(frozen=True, kw_only=True)
class ReferralLinksDto:
    # None = the bot isn't configured / no web cabinet URL is set
    bot_url: Optional[str] = None
    webcabinet_url: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class DownlineEntryDto:
    referred_id: int
    parent_id: int
    # relative to the user whose downline this is
    depth: int
    created_at: Optional[datetime]


@dataclass(frozen=True, kw_only=True)
class InvitedUserDto:
    user: Optional[UserDto]
    # who invited them directly, when that isn't the downline's owner
    via: Optional[UserDto]
    depth: int
    created_at: Optional[datetime]
    reward_amounts: dict[ReferralRewardType, Decimal]


@dataclass(frozen=True, kw_only=True)
class AdjustUserPointsDto:
    user_id: int
    delta: Decimal


@dataclass(frozen=True, kw_only=True)
class AssignReferralRewardsDto:
    user_id: int
    subscription_id: int
    is_new_purchase: bool
    payment_key: str


@dataclass(frozen=True, kw_only=True)
class AttachReferralOnRegistrationDto:
    user_id: int
    referral_code: str


@dataclass(frozen=True, kw_only=True)
class GetReferralSummaryDto:
    level: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    has_rewards: Optional[bool] = None
    reward_type: Optional[ReferralRewardType] = None


@dataclass(frozen=True, kw_only=True)
class ListInvitedUsersDto:
    user_id: int
    level: Optional[int] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class ListReferralsDto:
    level: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    has_rewards: Optional[bool] = None
    reward_type: Optional[ReferralRewardType] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class RequestPointsWithdrawalDto:
    amount: Decimal


@dataclass(frozen=True, kw_only=True)
class RedeemBonusDaysDto:
    subscription_id: int
    days: int


@dataclass(frozen=True, kw_only=True)
class BonusDaysRedemptionDto:
    subscription_id: int
    expire_at: datetime
    # balance left after the redemption
    bonus_days: int


@dataclass(frozen=True, kw_only=True)
class AdjustUserBonusDaysDto:
    user_id: int
    delta: int
