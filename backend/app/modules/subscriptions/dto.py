from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy
from remnapy.models.webhook import WebhookPayloadDto

from app.core.constants import DEFAULT_PAGE_SIZE, ZERO_AMOUNT
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    AddOnType,
    Currency,
    PanelSyncDirection,
    PlanBadge,
    PlanType,
    PurchaseType,
    SubscriptionStatus,
)
from app.modules.plans import PlanDto
from app.modules.subscriptions.events import StatusSyncSource


@dataclass(frozen=True, kw_only=True)
class PlanSnapshot:
    plan_id: int
    public_code: str
    name: str
    price_paid: Decimal
    currency: Currency
    duration_days: int
    # captured at checkout or redemption, so provisioning (NEW/CHANGE) never
    # looks the plan up again
    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    is_trial: bool
    internal_squads: list[UUID] = field(default_factory=list)
    external_squad: Optional[UUID] = None
    tag: Optional[str] = None
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
            "tag": self.tag,
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
            tag=data.get("tag"),
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
            tag=plan.tag,
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
    first_connected_at: Optional[datetime] = None
    paused_by_channel_leave: bool = False
    addon_entitlements: list[AddOnEntitlementDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class OwnSubscriptionUsageDto:
    subscription: SubscriptionDto
    used_traffic: Optional[int]


@dataclass(frozen=True, kw_only=True)
class SubscriptionListItemDto:
    subscription: SubscriptionDto
    # None once the account is deleted
    user_name: Optional[str]


@dataclass(frozen=True, kw_only=True)
class PanelSquadDto:
    uuid: UUID
    name: str
    kind: Literal["internal", "external"]


@dataclass(frozen=True, kw_only=True)
class SubscriptionDetailsDto:
    subscription: SubscriptionDto
    used_traffic: Optional[int]


@dataclass(frozen=True, kw_only=True)
class SubscriptionOverviewCountsDto:
    active: int
    limited: int
    expired: int
    disabled: int
    expiring: int
    paid_active: int
    active_trials: int


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
    # None above means "leave as is"; these were sent as null to empty them
    cleared: frozenset[str] = frozenset()


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
    # RENEW only: give the subscription the snapshot's tag; set for a checkout
    # order, whose snapshot is the plan as sold now, not the target's own
    apply_plan_tag: bool = False


@dataclass(frozen=True, kw_only=True)
class PurchaseRollbackDto:
    purchase_type: PurchaseType
    target_subscription_id: Optional[int]
    fulfilled_subscription_id: Optional[int]
    duration_days: int
    price_paid: Decimal
    currency: Currency
    has_later_paid_order: bool
    # the order's purchase key: a renewal that reached the panel but not the
    # database is found by the expiry pinned on it
    idempotency_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class RollbackPreviewDto:
    available: bool
    blocked_reason: Optional[str]
    old_term_expired: bool


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
class ProcessRemnawaveWebhookDto:
    # the body as the panel signed it, already verified by the api
    body: str


@dataclass(frozen=True, kw_only=True)
class PanelConfigDto:
    """What the panel holds for a user, in the subscription row's terms; the
    limits are the effective ones, add-ons included."""

    url: str
    traffic_limit: int  # GB, 0 = unlimited
    device_limit: int  # 0 = unlimited
    traffic_limit_strategy: TrafficLimitStrategy
    tag: Optional[str]
    internal_squads: list[UUID]
    external_squad: Optional[UUID]


@dataclass(frozen=True, kw_only=True)
class SyncSubscriptionStatusDto:
    remnawave_user_id: int
    status: SubscriptionStatus
    source: StatusSyncSource
    expire_at: Optional[datetime] = None
    first_connected_at: Optional[datetime] = None
    # None: the source only knows status and dates
    config: Optional[PanelConfigDto] = None


class PanelSyncResultDto(BaseDto):
    direction: PanelSyncDirection
    checked: int
    updated: int
    failed: int
    # panel users gone (from panel only)
    missing: int
    # rows given a new panel user in place of a gone one (to panel only)
    recreated: int = 0
    # rows made for a shop user's panel user without one (from panel only)
    imported: int = 0
    # shop users' panel users without a row, deleted (to panel only)
    deleted: int = 0
    finished_at: datetime


class PanelSyncStatusDto(BaseDto):
    direction: PanelSyncDirection
    running: bool
    last: Optional[PanelSyncResultDto] = None


class PanelSyncStatusesDto(BaseDto):
    from_panel: PanelSyncStatusDto
    to_panel: PanelSyncStatusDto


class PanelFieldDiffDto(BaseDto):
    field: str
    shop: str
    panel: str


@dataclass(frozen=True, kw_only=True)
class DeletedSubscriptionsDto:
    deleted: int


class SubscriptionPanelDiffDto(BaseDto):
    subscription_id: int
    missing_in_panel: bool
    fields: list[PanelFieldDiffDto]


@dataclass(frozen=True, kw_only=True)
class SubscriptionConfigUpdateDto:
    subscription_id: int
    url: str
    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    tag: Optional[str]
    internal_squads: list[UUID]
    external_squad: Optional[UUID]
    # add-on types whose grants the panel's lower limit overrode
    removed_addon_types: frozenset[AddOnType]


@dataclass(frozen=True, kw_only=True)
class PublishPanelEventDto:
    payload: WebhookPayloadDto


@dataclass(frozen=True, kw_only=True)
class CatalogPriceDto:
    currency: Currency
    price: Decimal
    # the price with the plan's running promotion off it, None while there is none
    discounted_price: Optional[Decimal] = None


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
    badge: Optional[PlanBadge]
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy
    traffic_limit: int
    device_limit: int
    is_trial: bool
    order_index: int
    durations: list[CatalogDurationDto]
    # the plan's promotion running now: 0 and None while there is none
    discount_percent: int = 0
    discount_ends_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class ListActivePlansDto:
    # a plan's public code: the catalog shrinks to that one plan, LINK plans included
    plan_code: Optional[str] = None
    # the catalog shrinks to that subscription's plan, whatever its availability
    renew_subscription_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class PlanCatalogDto:
    plans: list[CatalogPlanDto]
    anchor_currency: Currency


@dataclass(frozen=True, kw_only=True)
class SubscriptionRefDto:
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class DeleteDeviceDto:
    subscription_id: int
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
    # the trial's one duration, priced in the anchor currency; 0 for a free trial
    price: Decimal = ZERO_AMOUNT
    currency: Optional[Currency] = None
    # the same duration in every currency, as the catalog prices it: a paid trial
    # is checked out in whichever currency the chosen gateway takes
    prices: tuple[CatalogPriceDto, ...] = ()

    @property
    def is_free(self) -> bool:
        return self.price == 0


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


@dataclass(frozen=True, kw_only=True)
class ChannelMembershipDto:
    telegram_id: int
    chat_id: int
    joined: bool
