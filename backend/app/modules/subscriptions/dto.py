from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import Field
from remnapy.enums import TrafficLimitStrategy

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AddOnType, Currency, PurchaseType, SubscriptionStatus


@dataclass(frozen=True, kw_only=True)
class PlanSnapshot:
    plan_id: int
    public_code: str
    name: str
    price_paid: Decimal
    currency: Currency
    duration_days: int

    def to_json(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "public_code": self.public_code,
            "name": self.name,
            "price_paid": str(self.price_paid),
            "currency": self.currency.value,
            "duration_days": self.duration_days,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PlanSnapshot":
        return cls(
            plan_id=data["plan_id"],
            public_code=data["public_code"],
            name=data["name"],
            price_paid=Decimal(data["price_paid"]),
            currency=Currency(data["currency"]),
            duration_days=data["duration_days"],
        )


class AddOnEntitlementDto(BaseDto, TimestampMixin):
    subscription_id: int
    addon_id: Optional[int] = None
    type: AddOnType
    amount: int
    granted_at: datetime


class SubscriptionDto(BaseDto, TimestampMixin):
    user_id: int
    remnawave_user_id: int
    status: SubscriptionStatus
    is_trial: bool = False
    traffic_limit: int
    device_limit: int
    # Computed at read time from traffic_limit/device_limit + addon_entitlements
    # (spec §4.2: "effective limits are computed, not stored") -- never a DB column.
    effective_traffic_limit: int
    effective_device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    tag: Optional[str] = None
    internal_squads: list[UUID] = Field(default_factory=list)
    external_squad: Optional[UUID] = None
    expire_at: datetime
    url: str
    plan_snapshot: PlanSnapshot
    device_single_reset_at: Optional[datetime] = None
    device_all_reset_at: Optional[datetime] = None
    link_reset_at: Optional[datetime] = None
    addon_entitlements: list[AddOnEntitlementDto] = Field(default_factory=list)


class AddOnPriceDto(BaseDto):
    currency: Currency
    price: Decimal


class AddOnDto(BaseDto, TimestampMixin):
    name: str
    type: AddOnType
    amount: int
    order_index: int = 0
    is_active: bool = False
    prices: list[AddOnPriceDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CreateSubscriptionDto:
    """Internal plumbing: not wired to any usecase in this plan. Exists so the
    purchase plan (a separate plan) can call SubscriptionRepository.create()
    unchanged, and so this plan's own tests can build fixtures directly."""

    user_id: int
    remnawave_user_id: int
    status: SubscriptionStatus
    traffic_limit: int
    device_limit: int
    expire_at: datetime
    url: str
    plan_snapshot: PlanSnapshot
    traffic_limit_strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET
    is_trial: bool = False
    tag: Optional[str] = None
    internal_squads: list[UUID] = field(default_factory=list)
    external_squad: Optional[UUID] = None


@dataclass(frozen=True, kw_only=True)
class UpdateSubscriptionDto:
    subscription_id: int
    tag: Optional[str] = None
    traffic_limit: Optional[int] = None
    device_limit: Optional[int] = None
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None


@dataclass(frozen=True, kw_only=True)
class UpdateSubscriptionSquadsDto:
    subscription_id: int
    internal_squads: list[UUID]
    external_squad: Optional[UUID]


@dataclass(frozen=True, kw_only=True)
class CreateAddOnDto:
    name: str
    type: AddOnType
    amount: int


@dataclass(frozen=True, kw_only=True)
class UpdateAddOnDto:
    addon_id: int
    name: Optional[str] = None
    type: Optional[AddOnType] = None
    amount: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class SetAddOnPriceDto:
    currency: Currency
    price: Decimal


@dataclass(frozen=True, kw_only=True)
class SetAddOnPricesDto:
    addon_id: int
    prices: list[SetAddOnPriceDto]


@dataclass(frozen=True, kw_only=True)
class ReorderAddOnsDto:
    addon_ids: list[int]


@dataclass(frozen=True, kw_only=True)
class PurchaseSubscriptionDto:
    user_id: int
    plan_id: int
    duration_days: int
    # No real payment integration exists yet (modules/gateways has no
    # transaction model) -- price_paid/currency are supplied directly by the
    # caller for now, standing in for what a future gateway price-quote step
    # will compute. Deviates from spec §5.1's literal DTO (which has no price
    # field, assuming a payment step already existed) for exactly this reason.
    price_paid: Decimal
    currency: Currency
    purchase_type: PurchaseType
    target_subscription_id: Optional[int] = None
    idempotency_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class GrantAddOnDto:
    subscription_id: int
    addon_id: int


@dataclass(frozen=True, kw_only=True)
class SyncSubscriptionStatusDto:
    remnawave_user_id: int
    status: SubscriptionStatus
    source: str
