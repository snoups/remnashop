from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional, TypeAlias

from pydantic import AliasPath, BaseModel, Field

from app.core.enums import (
    Currency,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from app.modules.referrals.dto import MAX_BONUS_DAYS

# the points columns are Numeric(12, 0)
_WholeDecimal: TypeAlias = Annotated[Decimal, Field(max_digits=12, decimal_places=0)]


class ReferralSettingsResponse(BaseModel):
    enabled: bool
    max_level: int
    accrual_strategy: ReferralAccrualStrategy
    reward_type: ReferralRewardType
    reward_strategy: ReferralRewardStrategy
    reward_amounts: dict[int, Decimal]
    days_require_paid_subscription: bool
    invitee_reward_type: ReferralRewardType
    invitee_reward_amount: int
    anchor_currency: Optional[Currency]


class UpdateReferralSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    max_level: Optional[int] = Field(default=None, ge=1, le=3)
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
    reward_strategy: Optional[ReferralRewardStrategy] = None
    reward_amounts: Optional[dict[int, _WholeDecimal]] = None
    days_require_paid_subscription: Optional[bool] = None
    invitee_reward_type: Optional[ReferralRewardType] = None
    invitee_reward_amount: Optional[int] = Field(default=None, ge=0, le=MAX_BONUS_DAYS)


class ReferralUserResponse(BaseModel):
    id: int
    name: str
    username: Optional[str]
    telegram_id: Optional[int]
    email: Optional[str]


class ReferralRewardResponse(BaseModel):
    type: ReferralRewardType
    amount: Decimal
    created_at: Optional[datetime]
    # admin view only
    buyer: Optional[ReferralUserResponse] = None
    level: Optional[int] = None


class ReferralRevenueResponse(BaseModel):
    amount: Decimal
    currency: Currency
    paying_count: int


class ReferralStatsResponse(BaseModel):
    referral_code: Optional[str]
    referrer_id: Optional[int]
    points: Decimal
    bonus_days: int
    counts_by_level: dict[int, int]
    rewards: list[ReferralRewardResponse]
    # admin view only
    referrer: Optional[ReferralUserResponse] = None


class ReferralProgramResponse(BaseModel):
    enabled: bool
    reward_type: ReferralRewardType
    reward_strategy: ReferralRewardStrategy
    reward_amounts: dict[int, Decimal]
    invitee_reward_type: ReferralRewardType
    invitee_reward_amount: int
    accrual_strategy: ReferralAccrualStrategy
    max_level: int


class OwnReferralStatsResponse(ReferralStatsResponse):
    program: ReferralProgramResponse


class ReferralListItemResponse(BaseModel):
    id: int = Field(validation_alias=AliasPath("referral", "id"))
    level: int = Field(validation_alias=AliasPath("referral", "level"))
    created_at: Optional[datetime] = Field(validation_alias=AliasPath("referral", "created_at"))
    referred: Optional[ReferralUserResponse]
    referrer: Optional[ReferralUserResponse]
    reward_count: int = Field(validation_alias=AliasPath("rewards", "count"))
    reward_amounts: dict[ReferralRewardType, Decimal] = Field(
        validation_alias=AliasPath("rewards", "amounts")
    )


class ReferralPageResponse(BaseModel):
    items: list[ReferralListItemResponse]
    total: int


class ReferralSummaryResponse(BaseModel):
    total_count: int
    referrers_count: int
    rewarded_count: int
    conversion_rate: Decimal
    reward_amounts: dict[ReferralRewardType, Decimal]


class AdjustPointsRequest(BaseModel):
    delta: _WholeDecimal


class AdjustBonusDaysRequest(BaseModel):
    delta: int = Field(ge=-MAX_BONUS_DAYS, le=MAX_BONUS_DAYS)


class WithdrawPointsRequest(BaseModel):
    amount: _WholeDecimal = Field(gt=0)


class RedeemBonusDaysRequest(BaseModel):
    subscription_id: int
    days: int = Field(ge=1, le=MAX_BONUS_DAYS)


class RedeemBonusDaysResponse(BaseModel):
    subscription_id: int
    expire_at: datetime
    bonus_days: int
    pending: bool


class InvitedUserResponse(BaseModel):
    user: Optional[ReferralUserResponse]
    via: Optional[ReferralUserResponse]
    level: int = Field(validation_alias="depth")
    created_at: Optional[datetime]
    reward_amounts: dict[ReferralRewardType, Decimal]


class InvitedUserPageResponse(BaseModel):
    items: list[InvitedUserResponse]
    total: int
