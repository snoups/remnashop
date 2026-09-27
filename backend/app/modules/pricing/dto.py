from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Currency, PriceAdjustScope, RoundingMode
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
            raise ValidationError(f"No currency rate row for {c}")
        return row


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


class PriceBookCell(BaseDto):
    currency: Currency
    amount: Decimal
    is_pinned: bool


class PriceBookRow(BaseDto):
    kind: Literal["plan_duration", "addon"]
    ref_id: int
    plan_id: Optional[int] = None
    label: str
    days: Optional[int]
    base_price: Decimal
    cells: list[PriceBookCell]


class PriceBookDto(BaseDto):
    rate_table: list[CurrencyRateDto]
    settings: PricingSettingsDto
    plans: list[PriceBookRow]
    addons: list[PriceBookRow]


@dataclass(frozen=True, kw_only=True)
class SwitchAnchorCurrencyDto:
    new_anchor: Currency


@dataclass(frozen=True, kw_only=True)
class AdjustBasePricesDto:
    scope: PriceAdjustScope
    factor: Decimal
    plan_duration_ids: list[int] = field(default_factory=list)
    addon_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class PricingChangePreviewDto:
    # Exactly one of these three is set by the caller -- the usecase validates that.
    rate: Optional[UpdateCurrencyRateDto] = None
    anchor: Optional[Currency] = None
    adjust: Optional[AdjustBasePricesDto] = None


class PricingDiffRow(BaseDto):
    label: str
    currency: Currency
    old: Decimal
    new: Decimal


class PricingDiffDto(BaseDto):
    changes: list[PricingDiffRow]
    affected_count: int
