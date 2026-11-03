from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import PANEL_TAG_MAX_LENGTH, PANEL_TAG_PATTERN
from app.core.enums import (
    AddOnType,
    Currency,
    PlanAvailability,
    PlanBadge,
    PlanType,
    PriceAdjustScope,
    RoundingMode,
)

MATRIX_MAX_EDITS: Final[int] = 2000


class PlanPriceRequest(BaseModel):
    currency: Currency
    price: Decimal = Field(gt=0)


class PlanPriceResponse(BaseModel):
    currency: Currency
    price: Decimal


class PlanDurationRequest(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    # 0 only on a trial plan, checked by SetPlanDurationsUseCase
    base_price: Decimal = Field(ge=0)
    overrides: list[PlanPriceRequest] = Field(default_factory=list)


class PlanDurationResponse(BaseModel):
    days: int
    order_index: int
    base_price: Decimal
    overrides: list[PlanPriceResponse]


class PlanShareUrlsResponse(BaseModel):
    bot_url: Optional[str] = None
    webcabinet_url: Optional[str] = None


class PlanResponse(BaseModel):
    id: int
    public_code: str
    name: str
    description: Optional[str] = None
    tag: Optional[str] = None
    badge: Optional[PlanBadge] = None
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
    discount_percent: int
    discount_starts_at: Optional[datetime] = None
    discount_ends_at: Optional[datetime] = None
    durations: list[PlanDurationResponse]


class CreatePlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    tag: Optional[str] = Field(
        default=None, max_length=PANEL_TAG_MAX_LENGTH, pattern=PANEL_TAG_PATTERN
    )
    # shown to customers on the plan's card
    badge: Optional[PlanBadge] = None
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
    tag: Optional[str] = Field(
        default=None, max_length=PANEL_TAG_MAX_LENGTH, pattern=PANEL_TAG_PATTERN
    )
    # shown to customers on the plan's card
    badge: Optional[PlanBadge] = None
    type: Optional[PlanType] = None
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None
    traffic_limit: Optional[int] = Field(default=None, ge=0)
    device_limit: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    is_trial: Optional[bool] = None
    allow_bonus_days: Optional[bool] = None
    allow_promocodes: Optional[bool] = None


class SetPlanDurationsRequest(BaseModel):
    durations: list[PlanDurationRequest]


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


class UpdatePlanDiscountRequest(BaseModel):
    discount_percent: int = Field(ge=0, le=100)
    discount_starts_at: Optional[datetime] = None
    discount_ends_at: Optional[datetime] = None


class ReorderPlansRequest(BaseModel):
    plan_ids: list[int]


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    total: int


class AddOnPriceResponse(BaseModel):
    currency: Currency
    price: Decimal


class AddOnResponse(BaseModel):
    id: int
    name: str
    type: AddOnType
    amount: int
    order_index: int
    is_active: bool
    base_price: Decimal
    overrides: list[AddOnPriceResponse]


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


class AddOnListResponse(BaseModel):
    items: list[AddOnResponse]
    total: int


class CurrencyRateResponse(BaseModel):
    currency: Currency
    rate: Decimal
    rounding_mode: RoundingMode
    charm_ending: Optional[int] = None
    min_amount: Decimal


class PricingSettingsResponse(BaseModel):
    anchor_currency: Currency
    price_per_day: Optional[Decimal] = None
    price_per_gb: Optional[Decimal] = None


class PriceBookCellResponse(BaseModel):
    currency: Currency
    amount: Decimal
    is_pinned: bool


class PriceBookRowResponse(BaseModel):
    kind: Literal["plan_duration", "addon"]
    ref_id: int
    plan_id: Optional[int] = None
    name: str
    days: Optional[int] = None
    base_price: Decimal
    cells: list[PriceBookCellResponse]


class PriceBookResponse(BaseModel):
    rate_table: list[CurrencyRateResponse]
    settings: PricingSettingsResponse
    plans: list[PriceBookRowResponse]
    addons: list[PriceBookRowResponse]


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


class MatrixPlanBasePriceRequest(BaseModel):
    plan_id: int
    days: int
    base_price: Decimal = Field(gt=0)


class MatrixPlanOverrideRequest(BaseModel):
    plan_id: int
    days: int
    currency: Currency
    price: Optional[Decimal] = Field(default=None, gt=0)


class MatrixAddOnBasePriceRequest(BaseModel):
    addon_id: int
    base_price: Decimal = Field(gt=0)


class MatrixAddOnOverrideRequest(BaseModel):
    addon_id: int
    currency: Currency
    price: Optional[Decimal] = Field(default=None, gt=0)


class SetMatrixPricesRequest(BaseModel):
    plan_base_prices: list[MatrixPlanBasePriceRequest] = Field(
        default_factory=list, max_length=MATRIX_MAX_EDITS
    )
    plan_overrides: list[MatrixPlanOverrideRequest] = Field(
        default_factory=list, max_length=MATRIX_MAX_EDITS
    )
    addon_base_prices: list[MatrixAddOnBasePriceRequest] = Field(
        default_factory=list, max_length=MATRIX_MAX_EDITS
    )
    addon_overrides: list[MatrixAddOnOverrideRequest] = Field(
        default_factory=list, max_length=MATRIX_MAX_EDITS
    )


class AdjustBasePricesRequest(BaseModel):
    scope: PriceAdjustScope
    factor: Decimal = Field(gt=0)
    plan_duration_ids: list[int] = Field(default_factory=list)
    addon_ids: list[int] = Field(default_factory=list)


class PreviewRateChangeRequest(BaseModel):
    currency: Currency
    rate: Decimal = Field(gt=0)
    rounding_mode: RoundingMode
    charm_ending: Optional[int] = Field(default=None, ge=0, le=99)
    min_amount: Decimal = Field(gt=0)


class PreviewPricingChangeRequest(BaseModel):
    rate: Optional[PreviewRateChangeRequest] = None
    anchor: Optional[Currency] = None
    adjust: Optional[AdjustBasePricesRequest] = None


class PricingDiffRowResponse(BaseModel):
    name: str
    days: Optional[int] = None
    currency: Currency
    old: Decimal
    new: Decimal


class ScaledAmountResponse(BaseModel):
    old: Decimal
    new: Decimal


class PricingDiffResponse(BaseModel):
    changes: list[PricingDiffRowResponse]
    affected_count: int
    price_per_day: Optional[ScaledAmountResponse] = None
    price_per_gb: Optional[ScaledAmountResponse] = None
    loyalty_thresholds: list[ScaledAmountResponse]
    rescaled_transactions: int
