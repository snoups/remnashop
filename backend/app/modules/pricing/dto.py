from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Currency, RoundingMode
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

RATE_PRECISION: Final[Decimal] = Decimal("0.000001")
BASE_PRICE_PRECISION: Final[Decimal] = Decimal("0.01")
MIN_BASE_PRICE: Final[Decimal] = Decimal("0.01")
NON_ANCHOR_CURRENCIES: Final[frozenset[Currency]] = frozenset({Currency.XTR})


class CurrencyRateDto(BaseDto):
    currency: Currency
    rate: Decimal
    rounding_mode: RoundingMode
    charm_ending: Optional[int]
    min_amount: Decimal


@dataclass(frozen=True)
class CurrencyRateTable:
    anchor: Currency
    rows: dict[Currency, CurrencyRateDto] = field(default_factory=dict)

    def for_currency(self, c: Currency) -> CurrencyRateDto:
        row = self.rows.get(c)
        if row is None:
            raise ValidationError(
                f"No currency rate row for {c}", code=ErrorCode.CURRENCY_RATE_MISSING
            )
        return row

    def convert(self, amount: Decimal, source: Currency, target: Currency) -> Decimal:
        # exact, through the anchor; callers that show the result round it themselves
        if source is target:
            return amount
        return amount / self.for_currency(source).rate * self.for_currency(target).rate


class PricingSettingsDto(BaseDto, TimestampMixin):
    anchor_currency: Currency
    price_per_day: Optional[Decimal] = None
    price_per_gb: Optional[Decimal] = None


@dataclass(frozen=True, kw_only=True)
class UpdateCurrencyRateDto:
    currency: Currency
    rate: Decimal
    rounding_mode: RoundingMode
    charm_ending: Optional[int]
    min_amount: Decimal


@dataclass(frozen=True, kw_only=True)
class UpdatePricingSettingsDto:
    price_per_day: Optional[Decimal] = None
    price_per_gb: Optional[Decimal] = None
