from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import Currency, PlanAvailability, PlanType
from app.modules.plans.dto import PlanDurationDto
from app.modules.pricing import CurrencyRateTable, resolve_price


class PlanPriceItem(BaseModel):
    currency: Currency
    price: Decimal = Field(gt=0)


class PlanDurationItem(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    base_price: Decimal = Field(gt=0)
    overrides: list[PlanPriceItem] = Field(default_factory=list)


def to_duration_items(durations: list[PlanDurationDto]) -> list[PlanDurationItem]:
    return [
        PlanDurationItem(
            days=duration.days,
            order_index=duration.order_index,
            base_price=duration.base_price,
            overrides=[
                PlanPriceItem(currency=override.currency, price=override.price)
                for override in duration.overrides
            ],
        )
        for duration in durations
    ]


class PublicPlanDurationItem(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    prices: list[PlanPriceItem]


def to_public_duration_items(
    durations: list[PlanDurationDto], rates: CurrencyRateTable
) -> list[PublicPlanDurationItem]:
    return [
        PublicPlanDurationItem(
            days=duration.days,
            order_index=duration.order_index,
            prices=[
                PlanPriceItem(
                    currency=currency,
                    price=resolve_price(
                        duration.base_price,
                        currency,
                        next((o.price for o in duration.overrides if o.currency == currency), None),
                        rates,
                    ),
                )
                for currency in Currency
            ],
        )
        for duration in durations
    ]


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
    durations: list[PlanDurationItem]


class PublicPlanResponse(BaseModel):
    id: int
    public_code: str
    name: str
    description: Optional[str] = None
    tag: Optional[str] = None
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy
    traffic_limit: int
    device_limit: int
    is_trial: bool
    order_index: int
    durations: list[PublicPlanDurationItem]


class CreatePlanRequest(BaseModel):
    public_code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    tag: Optional[str] = Field(default=None, max_length=32)
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    traffic_limit: int = Field(ge=0)
    device_limit: int = Field(ge=0)
    is_trial: bool = False


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
