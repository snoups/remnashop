from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import (
    AddOnType,
    Currency,
    PlanAvailability,
    PlanType,
    PriceAdjustScope,
    RoundingMode,
)
from app.modules.plans.dto import PriceBookDto, PricingDiffDto
from app.modules.plans.dto import PriceBookRow as PriceBookRowDto


class PlanPriceItem(BaseModel):
    currency: Currency
    price: Decimal = Field(gt=0)


class PlanDurationItem(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    base_price: Decimal = Field(gt=0)
    overrides: list[PlanPriceItem] = Field(default_factory=list)


class PlanResponse(BaseModel):
    id: int
    public_code: str
    name: str
    description: Optional[str] = None
    tag: Optional[str] = None
    type: PlanType
    availability: PlanAvailability
    traffic_limit_strategy: TrafficLimitStrategy
    traffic_limit: int
    device_limit: int
    allowed_telegram_ids: list[int]
    allowed_emails: list[str]
    internal_squads: list[UUID]
    external_squad: Optional[UUID] = None
    order_index: int
    is_active: bool
    is_trial: bool
    allow_bonus_days: bool
    allow_promocodes: bool
    durations: list[PlanDurationItem]


class CreatePlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    tag: Optional[str] = Field(default=None, max_length=32)
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    traffic_limit: int = Field(ge=0)
    device_limit: int = Field(ge=0)
    is_trial: bool = False
    allow_bonus_days: bool = True
    allow_promocodes: bool = True


class UpdatePlanRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    tag: Optional[str] = Field(default=None, max_length=32)
    type: Optional[PlanType] = None
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None
    traffic_limit: Optional[int] = Field(default=None, ge=0)
    device_limit: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    is_trial: Optional[bool] = None
    allow_bonus_days: Optional[bool] = None
    allow_promocodes: Optional[bool] = None


class SetPlanDurationsRequest(BaseModel):
    durations: list[PlanDurationItem]


class SetPlanPriceOverrideRequest(BaseModel):
    price: Optional[Decimal] = Field(default=None, gt=0)


class SetPlanDurationBasePriceRequest(BaseModel):
    base_price: Decimal = Field(gt=0)


class UpdatePlanAccessRequest(BaseModel):
    availability: PlanAvailability
    allowed_telegram_ids: list[int] = Field(default_factory=list)
    allowed_emails: list[str] = Field(default_factory=list)


class UpdatePlanSquadsRequest(BaseModel):
    internal_squads: list[UUID] = Field(default_factory=list)
    external_squad: Optional[UUID] = None


class ReorderPlansRequest(BaseModel):
    plan_ids: list[int]


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    total: int


class AddOnPriceItem(BaseModel):
    currency: Currency
    price: Decimal = Field(gt=0)


class AddOnResponse(BaseModel):
    id: int
    name: str
    type: AddOnType
    amount: int
    order_index: int
    is_active: bool
    base_price: Decimal
    overrides: list[AddOnPriceItem]


class CreateAddOnRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AddOnType
    amount: int = Field(gt=0)
    base_price: Decimal = Field(gt=0)


class UpdateAddOnRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    type: Optional[AddOnType] = None
    amount: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None


class SetAddOnBasePriceRequest(BaseModel):
    base_price: Decimal = Field(gt=0)


class SetAddOnPriceOverrideRequest(BaseModel):
    price: Optional[Decimal] = Field(default=None, gt=0)


class ReorderAddOnsRequest(BaseModel):
    addon_ids: list[int]


class AddOnListResponse(BaseModel):
    items: list[AddOnResponse]
    total: int


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
        cells=[PriceBookCellItem.model_validate(cell, from_attributes=True) for cell in row.cells],
    )


def to_price_book_response(book: PriceBookDto) -> PriceBookResponse:
    return PriceBookResponse(
        rate_table=[
            CurrencyRateItem.model_validate(row, from_attributes=True) for row in book.rate_table
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
            PricingDiffRowItem.model_validate(row, from_attributes=True) for row in diff.changes
        ],
        affected_count=diff.affected_count,
    )
