from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AddOnType, Currency, PlanType, PurchaseType, SubscriptionStatus
from app.modules.plans import PlanDto


@dataclass(frozen=True, kw_only=True)
class PlanSnapshot:
    plan_id: int
    public_code: str
    name: str
    price_paid: Decimal
    currency: Currency
    duration_days: int
    # Operational fields, needed to actually provision a Remnawave panel user
    # (NEW/CHANGE) without a live PlanRepository lookup at provisioning time --
    # captured once, at checkout/redemption time, when the plan is known to
    # still exist and be purchasable. See usecases/purchase_subscription/.
    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    is_trial: bool
    internal_squads: list[UUID] = field(default_factory=list)
    external_squad: Optional[UUID] = None
    # money and days behind the current credit, accumulated by RENEW and grants since
    # the last NEW/CHANGE; None on a snapshot written before they existed
    credit_paid: Optional[Decimal] = None
    credit_days: Optional[int] = None

    @property
    def effective_credit_paid(self) -> Decimal:
        return self.credit_paid if self.credit_paid is not None else self.price_paid

    @property
    def effective_credit_days(self) -> int:
        return self.credit_days if self.credit_days is not None else self.duration_days

    def to_json(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "public_code": self.public_code,
            "name": self.name,
            "price_paid": str(self.price_paid),
            "currency": self.currency.value,
            "duration_days": self.duration_days,
            "traffic_limit": self.traffic_limit,
            "device_limit": self.device_limit,
            "traffic_limit_strategy": self.traffic_limit_strategy.value,
            "is_trial": self.is_trial,
            "internal_squads": [str(squad) for squad in self.internal_squads],
            "external_squad": str(self.external_squad) if self.external_squad else None,
            "credit_paid": str(self.credit_paid) if self.credit_paid is not None else None,
            "credit_days": self.credit_days,
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
            traffic_limit=data["traffic_limit"],
            device_limit=data["device_limit"],
            traffic_limit_strategy=TrafficLimitStrategy(data["traffic_limit_strategy"]),
            is_trial=data["is_trial"],
            internal_squads=[UUID(squad) for squad in data["internal_squads"]],
            external_squad=UUID(data["external_squad"]) if data["external_squad"] else None,
            credit_paid=(
                Decimal(data["credit_paid"]) if data.get("credit_paid") is not None else None
            ),
            credit_days=data.get("credit_days"),
        )

    @classmethod
    def from_plan(
        cls,
        plan: PlanDto,
        *,
        price_paid: Decimal,
        currency: Currency,
        duration_days: int,
        is_trial: bool = False,
    ) -> "PlanSnapshot":
        return cls(
            plan_id=plan.id,
            public_code=plan.public_code,
            name=plan.name,
            price_paid=price_paid,
            currency=currency,
            duration_days=duration_days,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            traffic_limit_strategy=plan.traffic_limit_strategy,
            is_trial=plan.is_trial or is_trial,
            internal_squads=plan.internal_squads,
            external_squad=plan.external_squad,
            credit_paid=price_paid,
            credit_days=duration_days,
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
    # traffic_limit/device_limit plus addon_entitlements, computed at read time
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


@dataclass(frozen=True, kw_only=True)
class LiveSubscriptionDto:
    user_id: int
    is_trial: bool
    status: SubscriptionStatus
    expire_at: datetime
    plan_name: str
    price_paid: Decimal
    currency: Currency
    duration_days: int


@dataclass(frozen=True, kw_only=True)
class CreateSubscriptionDto:
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
    expire_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class UpdateSubscriptionSquadsDto:
    subscription_id: int
    internal_squads: list[UUID]
    external_squad: Optional[UUID]


@dataclass(frozen=True, kw_only=True)
class PurchaseSubscriptionDto:
    user_id: int
    plan_snapshot: PlanSnapshot
    duration_days: int
    # price_paid is what the user actually paid (post-discount). base_price,
    # when set, is the undiscounted list price and is used as the CHANGE
    # proration denominator; None means "same as price_paid".
    price_paid: Decimal
    base_price: Optional[Decimal] = None
    currency: Currency
    purchase_type: PurchaseType
    target_subscription_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    # set by PurchaseSubscriptionUseCase from its own claim of idempotency_key
    claim_token: Optional[datetime] = None
    # False for a paid checkout order: the cap was enforced at checkout, and
    # refusing after the charge leaves the customer paid with nothing. A free
    # order keeps it.
    enforce_subscription_cap: bool = True
    # False for a paid order too: a disabled target was refused at checkout,
    # and one disabled after the charge is still owed its renewal
    refuse_disabled_target: bool = True
    # False for an admin grant/plan change: the caller publishes its own
    # actor-and-target event instead of a purchase by the admin
    publish_event: bool = True
    # CHANGE only: keep the target's expire_at instead of now + days + credit
    keep_expire_at: bool = False
    # CHANGE only: zero the panel's traffic counter; set for a customer's paid
    # change, whose credit already deducts the spent traffic
    reset_traffic: bool = False


@dataclass(frozen=True, kw_only=True)
class GrantAddOnDto:
    subscription_id: int
    addon_id: int
    idempotency_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class GrantSubscriptionDto:
    user_id: int
    plan_id: int
    duration_days: int


@dataclass(frozen=True, kw_only=True)
class ChangeSubscriptionPlanDto:
    subscription_id: int
    plan_id: int
    # None keeps the current expire_at
    duration_days: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class RemnawaveWebhookDto:
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class SyncSubscriptionStatusDto:
    remnawave_user_id: int
    status: SubscriptionStatus
    source: str
    expire_at: Optional[datetime] = None
    first_connected_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class PublishLifecycleEventDto:
    remnawave_user_id: int
    webhook_event: str
    hours: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class CatalogPriceDto:
    currency: Currency
    price: Decimal


@dataclass(frozen=True, kw_only=True)
class CatalogDurationDto:
    days: int
    order_index: int
    prices: list[CatalogPriceDto]


@dataclass(frozen=True, kw_only=True)
class CatalogPlanDto:
    id: int
    name: str
    description: Optional[str]
    tag: Optional[str]
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy
    traffic_limit: int
    device_limit: int
    is_trial: bool
    order_index: int
    durations: list[CatalogDurationDto]


@dataclass(frozen=True, kw_only=True)
class ActivateTrialSubscriptionDto:
    plan: PlanDto


@dataclass(frozen=True, kw_only=True)
class DeleteDeviceDto:
    hwid: str


@dataclass(frozen=True, kw_only=True)
class AdminDeleteDeviceDto:
    subscription_id: int
    hwid: str


@dataclass(frozen=True, kw_only=True)
class SetSubscriptionEnabledDto:
    subscription_id: int
    enabled: bool


@dataclass(frozen=True, kw_only=True)
class GetAvailableTrialDto:
    plan: Optional[PlanDto]
    is_trial_available: bool


class DeviceDto(BaseModel):
    hwid: str
    platform: Optional[str]
    device_model: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class ListSubscriptionsDto:
    status: Optional[SubscriptionStatus] = None
    search: Optional[str] = None
    user_id: Optional[int] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
