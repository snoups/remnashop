from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field
from remnapy.enums import TrafficLimitStrategy

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AddOnType, Currency, PlanAvailability, PlanType, PriceAdjustScope
from app.modules.pricing import CurrencyRateDto, PricingSettingsDto, UpdateCurrencyRateDto


class PlanPriceOverrideDto(BaseDto):
    currency: Currency
    price: Decimal


class PlanDurationDto(BaseDto):
    id: int
    days: int
    order_index: int = 0
    base_price: Decimal
    overrides: list[PlanPriceOverrideDto] = Field(default_factory=list)


class PlanDto(BaseDto, TimestampMixin):
    public_code: str
    name: str
    description: Optional[str] = None
    tag: Optional[str] = None
    type: PlanType
    availability: PlanAvailability = PlanAvailability.ALL
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    traffic_limit: int
    device_limit: int
    allowed_telegram_ids: list[int] = Field(default_factory=list)
    allowed_emails: list[str] = Field(default_factory=list)
    internal_squads: list[UUID] = Field(default_factory=list)
    external_squad: Optional[UUID] = None
    order_index: int = 0
    is_active: bool = False
    is_trial: bool = False
    allow_bonus_days: bool = True
    allow_promocodes: bool = True
    discount_percent: int = 0
    discount_starts_at: Optional[datetime] = None
    discount_ends_at: Optional[datetime] = None
    durations: list[PlanDurationDto] = Field(default_factory=list)

    def active_discount(self, now: datetime) -> int:
        if self.discount_starts_at is not None and now < self.discount_starts_at:
            return 0
        if self.discount_ends_at is not None and now >= self.discount_ends_at:
            return 0
        return self.discount_percent


@dataclass(frozen=True, kw_only=True)
class CreatePlanDto:
    name: str
    type: PlanType
    traffic_limit: int
    device_limit: int
    description: Optional[str] = None
    tag: Optional[str] = None
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    is_trial: bool = False
    allow_bonus_days: bool = True
    allow_promocodes: bool = True
    # left unset by the API: CreatePlanUseCase generates it
    public_code: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class UpdatePlanDto:
    plan_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    tag: Optional[str] = None
    type: Optional[PlanType] = None
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None
    traffic_limit: Optional[int] = None
    device_limit: Optional[int] = None
    is_active: Optional[bool] = None
    is_trial: Optional[bool] = None
    allow_bonus_days: Optional[bool] = None
    allow_promocodes: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class SetPlanDurationDto:
    days: int
    order_index: int
    base_price: Decimal


@dataclass(frozen=True, kw_only=True)
class SetPlanDurationsDto:
    plan_id: int
    durations: list[SetPlanDurationDto]


@dataclass(frozen=True, kw_only=True)
class SetPlanPriceOverrideDto:
    plan_id: int
    days: int
    currency: Currency
    price: Optional[Decimal]


@dataclass(frozen=True, kw_only=True)
class SetPlanDurationBasePriceDto:
    plan_id: int
    days: int
    base_price: Decimal


@dataclass(frozen=True, kw_only=True)
class UpdatePlanAccessDto:
    plan_id: int
    availability: PlanAvailability
    allowed_telegram_ids: list[int]
    allowed_emails: list[str]


@dataclass(frozen=True, kw_only=True)
class UpdatePlanSquadsDto:
    plan_id: int
    internal_squads: list[UUID]
    external_squad: Optional[UUID]


@dataclass(frozen=True, kw_only=True)
class UpdatePlanDiscountDto:
    plan_id: int
    discount_percent: int
    discount_starts_at: Optional[datetime]
    discount_ends_at: Optional[datetime]


@dataclass(frozen=True, kw_only=True)
class ReorderPlansDto:
    plan_ids: list[int]


class AddOnPriceOverrideDto(BaseDto):
    currency: Currency
    price: Decimal


class AddOnDto(BaseDto, TimestampMixin):
    name: str
    type: AddOnType
    amount: int
    order_index: int = 0
    is_active: bool = False
    base_price: Decimal
    overrides: list[AddOnPriceOverrideDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CreateAddOnDto:
    name: str
    type: AddOnType
    amount: int
    base_price: Decimal


@dataclass(frozen=True, kw_only=True)
class UpdateAddOnDto:
    addon_id: int
    name: Optional[str] = None
    type: Optional[AddOnType] = None
    amount: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class SetAddOnBasePriceDto:
    addon_id: int
    base_price: Decimal


@dataclass(frozen=True, kw_only=True)
class SetAddOnPriceOverrideDto:
    addon_id: int
    currency: Currency
    price: Optional[Decimal]


class PriceBookCell(BaseDto):
    currency: Currency
    amount: Decimal
    is_pinned: bool


class PriceBookRow(BaseDto):
    kind: Literal["plan_duration", "addon"]
    ref_id: int
    plan_id: Optional[int] = None
    # plain plan/add-on name; the client adds the duration from `days` in its own language
    name: str
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
    # exactly one of the three is set; the usecase checks it
    rate: Optional[UpdateCurrencyRateDto] = None
    anchor: Optional[Currency] = None
    adjust: Optional[AdjustBasePricesDto] = None


class PricingDiffRow(BaseDto):
    # plain plan/add-on name; `days` is set for plan durations, None for add-ons
    name: str
    days: Optional[int] = None
    currency: Currency
    old: Decimal
    new: Decimal


class PricingDiffDto(BaseDto):
    changes: list[PricingDiffRow]
    affected_count: int
