from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional, TypeAlias

from pydantic import BaseModel, Field

from app.core.enums import (
    Currency,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)

_WholeDecimal: TypeAlias = Annotated[Decimal, Field(decimal_places=0)]


class ReferralSettingsResponse(BaseModel):
    enabled: bool
    max_level: int
    accrual_strategy: ReferralAccrualStrategy
    reward_type: ReferralRewardType
    reward_strategy: ReferralRewardStrategy
    reward_amounts: dict[int, Decimal]
    anchor_currency: Optional[Currency]


class UpdateReferralSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    max_level: Optional[int] = Field(default=None, ge=1, le=3)
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
    reward_strategy: Optional[ReferralRewardStrategy] = None
    reward_amounts: Optional[dict[int, _WholeDecimal]] = None


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
    counts_by_level: dict[int, int]
    rewards: list[ReferralRewardResponse]
    # admin view only
    referrer: Optional[ReferralUserResponse] = None


class ReferralLinksResponse(BaseModel):
    bot_url: Optional[str]
    webcabinet_url: Optional[str]


class ReferralListItemResponse(BaseModel):
    id: int
    level: int
    created_at: Optional[datetime]
    referred: Optional[ReferralUserResponse]
    referrer: Optional[ReferralUserResponse]
    reward_count: int
    reward_amounts: dict[ReferralRewardType, Decimal]


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


class AttachReferralRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class WithdrawPointsRequest(BaseModel):
    amount: _WholeDecimal = Field(gt=0)


class InvitedUserResponse(BaseModel):
    user: Optional[ReferralUserResponse]
    via: Optional[ReferralUserResponse]
    level: int
    created_at: Optional[datetime]
    reward_amounts: dict[ReferralRewardType, Decimal]


class InvitedUserPageResponse(BaseModel):
    items: list[InvitedUserResponse]
    total: int
