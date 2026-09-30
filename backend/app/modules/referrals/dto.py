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
    # not stored here: pricing's anchor, what a PERCENT points reward is counted in
    anchor_currency: Optional[Currency] = None


@dataclass(frozen=True, kw_only=True)
class ReferralRevenueDto:
    # what the user's downline has paid, converted to one report currency
    amount: Decimal
    currency: Currency
    paying_count: int


class ReferralStatsDto(BaseDto):
    referral_code: Optional[str] = None
    referrer_id: Optional[int] = None
    points: Decimal = Decimal(0)
    counts_by_level: dict[int, int] = field(default_factory=dict)
    rewards: list[ReferralRewardDto] = field(default_factory=list)
    # admin view only: the referrer and each reward's buyer, keyed by user id
    users: dict[int, UserDto] = field(default_factory=dict)
    # admin view only: each buyer's depth below this user
    buyer_levels: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class UpdateReferralSettingsDto:
    # None = leave unchanged, matching UpdateUserDto's convention.
    enabled: Optional[bool] = None
    max_level: Optional[int] = None
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
    reward_strategy: Optional[ReferralRewardStrategy] = None
    reward_amounts: Optional[dict[int, Decimal]] = None


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
