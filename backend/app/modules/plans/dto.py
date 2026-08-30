from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field
from remnapy.enums import TrafficLimitStrategy

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Currency, PlanAvailability, PlanType


class PlanPriceDto(BaseDto):
    currency: Currency
    price: Decimal


class PlanDurationDto(BaseDto):
    days: int
    order_index: int = 0
    prices: list[PlanPriceDto] = Field(default_factory=list)


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
    durations: list[PlanDurationDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CreatePlanDto:
    public_code: str
    name: str
    type: PlanType
    traffic_limit: int
    device_limit: int
    description: Optional[str] = None
    tag: Optional[str] = None
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    is_trial: bool = False


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


@dataclass(frozen=True, kw_only=True)
class SetPlanPriceDto:
    currency: Currency
    price: Decimal


@dataclass(frozen=True, kw_only=True)
class SetPlanDurationDto:
    days: int
    order_index: int
    prices: list[SetPlanPriceDto]


@dataclass(frozen=True, kw_only=True)
class SetPlanDurationsDto:
    plan_id: int
    durations: list[SetPlanDurationDto]


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
class ReorderPlansDto:
    plan_ids: list[int]
