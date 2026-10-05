from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LoyaltyTierSchema(BaseModel):
    threshold: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    percent: int = Field(ge=1, le=100)


class LoyaltySettingsRequest(BaseModel):
    enabled: bool
    window_months: Optional[int] = Field(ge=1, le=120)
    tiers: list[LoyaltyTierSchema] = Field(max_length=20)


class LoyaltySettingsResponse(BaseModel):
    enabled: bool
    window_months: Optional[int]
    tiers: list[LoyaltyTierSchema]
    currency: Optional[str]


class UserLoyaltyRequest(BaseModel):
    excluded: bool


class UserLoyaltyResponse(BaseModel):
    discount: int
    excluded: bool
    spent: Decimal
    next_tier: Optional[LoyaltyTierSchema]
    currency: str
