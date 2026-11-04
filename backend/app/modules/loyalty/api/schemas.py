from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LoyaltyTierRequest(BaseModel):
    threshold: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    percent: int = Field(ge=1, le=100)


class LoyaltyTierResponse(BaseModel):
    threshold: Decimal
    percent: int


class LoyaltySettingsRequest(BaseModel):
    enabled: bool
    window_months: Optional[int] = Field(ge=1, le=120)
    tiers: list[LoyaltyTierRequest] = Field(max_length=20)


class LoyaltySettingsResponse(BaseModel):
    enabled: bool
    window_months: Optional[int]
    tiers: list[LoyaltyTierResponse]
    currency: Optional[str] = Field(validation_alias="anchor_currency")


class UserLoyaltyRequest(BaseModel):
    excluded: bool


class UserLoyaltyResponse(BaseModel):
    discount: int
    excluded: bool
    is_program_active: bool
    spent: Decimal
    next_tier: Optional[LoyaltyTierResponse]
    currency: str
