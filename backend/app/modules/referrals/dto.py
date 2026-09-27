from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import ReferralAccrualStrategy, ReferralRewardType
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


class ReferralSettingsDto(BaseDto, TimestampMixin):
    enabled: bool = False
    max_level: int = 1
    accrual_strategy: ReferralAccrualStrategy = ReferralAccrualStrategy.FIRST_PAYMENT
    reward_type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    reward_amounts: dict[int, Decimal] = field(default_factory=dict)


class ReferralStatsDto(BaseDto):
    referral_code: Optional[str] = None
    referrer_id: Optional[int] = None
    points: Decimal = Decimal(0)
    counts_by_level: dict[int, int] = field(default_factory=dict)
    rewards: list[ReferralRewardDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class UpdateReferralSettingsDto:
    # None = leave unchanged, matching UpdateUserDto's convention.
    enabled: Optional[bool] = None
    max_level: Optional[int] = None
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
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
