from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.enums import Currency, PriceAdjustScope, RoundingMode
from app.modules.pricing.dto import PriceBookDto, PricingDiffDto
from app.modules.pricing.dto import PriceBookRow as PriceBookRowDto


class CurrencyRateItem(BaseModel):
    currency: Currency
    rate: Decimal
    rounding_mode: RoundingMode
    charm_ending: Optional[int] = None
    min_amount: Decimal


class PricingSettingsResponse(BaseModel):
    anchor_currency: Currency
    price_per_day: Optional[Decimal] = None
    price_per_gb: Optional[Decimal] = None


class PriceBookCellItem(BaseModel):
    currency: Currency
    amount: Decimal
    is_pinned: bool


class PriceBookRowItem(BaseModel):
    kind: Literal["plan_duration", "addon"]
    ref_id: int
    plan_id: Optional[int] = None
    name: str
    days: Optional[int] = None
    base_price: Decimal
    cells: list[PriceBookCellItem]


class PriceBookResponse(BaseModel):
    rate_table: list[CurrencyRateItem]
    settings: PricingSettingsResponse
    plans: list[PriceBookRowItem]
    addons: list[PriceBookRowItem]


def _to_row_item(row: PriceBookRowDto) -> PriceBookRowItem:
    return PriceBookRowItem(
        kind=row.kind,
        ref_id=row.ref_id,
        plan_id=row.plan_id,
        name=row.name,
        days=row.days,
        base_price=row.base_price,
        cells=[
            PriceBookCellItem(currency=cell.currency, amount=cell.amount, is_pinned=cell.is_pinned)
            for cell in row.cells
        ],
    )


def to_price_book_response(book: PriceBookDto) -> PriceBookResponse:
    return PriceBookResponse(
        rate_table=[
            CurrencyRateItem(
                currency=row.currency,
                rate=row.rate,
                rounding_mode=row.rounding_mode,
                charm_ending=row.charm_ending,
                min_amount=row.min_amount,
            )
            for row in book.rate_table
        ],
        settings=PricingSettingsResponse(
            anchor_currency=book.settings.anchor_currency,
            price_per_day=book.settings.price_per_day,
            price_per_gb=book.settings.price_per_gb,
        ),
        plans=[_to_row_item(row) for row in book.plans],
        addons=[_to_row_item(row) for row in book.addons],
    )


class UpdateCurrencyRateRequest(BaseModel):
    rate: Decimal = Field(gt=0)
    rounding_mode: RoundingMode
    charm_ending: Optional[int] = Field(default=None, ge=0, le=99)
    min_amount: Decimal = Field(gt=0)


class UpdatePricingSettingsRequest(BaseModel):
    price_per_day: Optional[Decimal] = Field(default=None, gt=0)
    price_per_gb: Optional[Decimal] = Field(default=None, gt=0)


class SwitchAnchorRequest(BaseModel):
    new_anchor: Currency


class AdjustBasePricesRequest(BaseModel):
    scope: PriceAdjustScope
    factor: Decimal = Field(gt=0)
    plan_duration_ids: list[int] = Field(default_factory=list)
    addon_ids: list[int] = Field(default_factory=list)


class PreviewRateChange(BaseModel):
    currency: Currency
    rate: Decimal = Field(gt=0)
    rounding_mode: RoundingMode
    charm_ending: Optional[int] = Field(default=None, ge=0, le=99)
    min_amount: Decimal = Field(gt=0)


class PreviewPricingChangeRequest(BaseModel):
    rate: Optional[PreviewRateChange] = None
    anchor: Optional[Currency] = None
    adjust: Optional[AdjustBasePricesRequest] = None


class PricingDiffRowItem(BaseModel):
    name: str
    days: Optional[int] = None
    currency: Currency
    old: Decimal
    new: Decimal


class PricingDiffResponse(BaseModel):
    changes: list[PricingDiffRowItem]
    affected_count: int


def to_diff_response(diff: PricingDiffDto) -> PricingDiffResponse:
    return PricingDiffResponse(
        changes=[
            PricingDiffRowItem(
                name=row.name, days=row.days, currency=row.currency, old=row.old, new=row.new
            )
            for row in diff.changes
        ],
        affected_count=diff.affected_count,
    )
