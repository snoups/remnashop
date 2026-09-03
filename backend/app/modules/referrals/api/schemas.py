from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import ReferralAccrualStrategy, ReferralRewardType


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
    reward_amounts: Optional[dict[int, Decimal]] = None


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


class AdjustPointsRequest(BaseModel):
    delta: Decimal


class AttachReferralRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class WithdrawPointsRequest(BaseModel):
    amount: Decimal = Field(gt=0)
