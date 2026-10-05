import calendar
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.loyalty.dto import LoyaltyTierDto

_MAX_PERCENT: Final[int] = 100


def resolve_percent(total: Decimal, tiers: list[LoyaltyTierDto]) -> int:
    return max((tier.percent for tier in tiers if tier.threshold <= total), default=0)


def next_tier(total: Decimal, tiers: list[LoyaltyTierDto]) -> Optional[LoyaltyTierDto]:
    return next((tier for tier in tiers if tier.threshold > total), None)


def months_before(moment: datetime, months: int) -> datetime:
    year, month = divmod(moment.year * 12 + moment.month - 1 - months, 12)
    day = min(moment.day, calendar.monthrange(year, month + 1)[1])
    return moment.replace(year=year, month=month + 1, day=day)


def validate_tiers(tiers: list[LoyaltyTierDto], window_months: Optional[int]) -> None:
    if window_months is not None and window_months < 1:
        raise ValidationError(
            "The window must be at least one month", code=ErrorCode.LOYALTY_TIERS_INVALID
        )
    for tier in tiers:
        if tier.threshold <= 0 or not 1 <= tier.percent <= _MAX_PERCENT:
            raise ValidationError(
                "A tier needs a positive threshold and a 1-100 percent",
                code=ErrorCode.LOYALTY_TIERS_INVALID,
            )
    for lower, upper in zip(tiers, tiers[1:]):
        if upper.threshold <= lower.threshold or upper.percent <= lower.percent:
            raise ValidationError(
                "Tier thresholds and percents must both increase",
                code=ErrorCode.LOYALTY_TIERS_INVALID,
            )
