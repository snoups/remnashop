from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional, TypeAlias

from pydantic import BaseModel, Field

from app.core.enums import ReferralAccrualStrategy, ReferralRewardType

_WholeDecimal: TypeAlias = Annotated[Decimal, Field(decimal_places=0)]


class ReferralSettingsResponse(BaseModel):
    enabled: bool
    max_level: int
    accrual_strategy: ReferralAccrualStrategy
    reward_type: ReferralRewardType
    reward_amounts: dict[int, Decimal]


class UpdateReferralSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    max_level: Optional[int] = Field(default=None, ge=1, le=3)
    accrual_strategy: Optional[ReferralAccrualStrategy] = None
    reward_type: Optional[ReferralRewardType] = None
    reward_amounts: Optional[dict[int, _WholeDecimal]] = None


class ReferralRewardResponse(BaseModel):
    type: ReferralRewardType
    amount: Decimal
    created_at: Optional[datetime]


class ReferralStatsResponse(BaseModel):
    referral_code: Optional[str]
    referrer_id: Optional[int]
    points: Decimal
    counts_by_level: dict[int, int]
    rewards: list[ReferralRewardResponse]


class ReferralUserResponse(BaseModel):
    id: int
    name: str
    username: Optional[str]
    telegram_id: Optional[int]


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


class AdjustPointsRequest(BaseModel):
    delta: _WholeDecimal


class AttachReferralRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class WithdrawPointsRequest(BaseModel):
    amount: _WholeDecimal = Field(gt=0)
