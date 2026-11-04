from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.core.enums import Currency


@dataclass(frozen=True, kw_only=True)
class LoyaltyTierDto:
    threshold: Decimal
    percent: int


@dataclass(frozen=True, kw_only=True)
class LoyaltySettingsDto:
    enabled: bool = False
    window_months: Optional[int] = None
    tiers: list[LoyaltyTierDto] = field(default_factory=list)
    # not stored here: pricing's anchor, what thresholds are counted in
    anchor_currency: Optional[Currency] = None


@dataclass(frozen=True, kw_only=True)
class UpdateLoyaltySettingsDto:
    # full replace: None in window_months means all time
    enabled: bool
    window_months: Optional[int]
    tiers: list[LoyaltyTierDto]


@dataclass(frozen=True, kw_only=True)
class RecalculateLoyaltyDto:
    # None = everyone
    user_ids: Optional[list[int]] = None


@dataclass(frozen=True, kw_only=True)
class UserLoyaltyDto:
    user_id: int
    discount: int
    excluded: bool
    is_program_active: bool
    spent: Decimal
    next_tier: Optional[LoyaltyTierDto]
    currency: Currency


@dataclass(frozen=True, kw_only=True)
class SetUserLoyaltyExcludedDto:
    user_id: int
    excluded: bool
