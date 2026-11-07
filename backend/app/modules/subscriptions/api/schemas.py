from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import PANEL_TAG_MAX_LENGTH, PANEL_TAG_PATTERN
from app.core.enums import (
    AddOnType,
    Currency,
    PanelSyncDirection,
    PlanBadge,
    PlanType,
    SubscriptionStatus,
)
from app.core.security.connect_signature import sign_subscription_url
from app.modules.subscriptions.dto import PlanSnapshot, SubscriptionDto


class AddOnEntitlementResponse(BaseModel):
    subscription_id: int
    addon_id: Optional[int] = None
    type: AddOnType
    amount: int
    granted_at: datetime


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    remnawave_user_id: int
    status: SubscriptionStatus
    is_trial: bool
    traffic_limit: int
    device_limit: int
    effective_traffic_limit: int
    effective_device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    tag: Optional[str] = None
    internal_squads: list[UUID]
    external_squad: Optional[UUID] = None
    expire_at: datetime
    created_at: Optional[datetime] = None
    first_connected_at: Optional[datetime] = None
    url: str
    plan_snapshot: dict[str, Any]
    device_single_reset_at: Optional[datetime] = None
    device_all_reset_at: Optional[datetime] = None
    link_reset_at: Optional[datetime] = None
    addon_entitlements: list[AddOnEntitlementResponse]

    @field_validator("plan_snapshot", mode="before")
    @classmethod
    def _snapshot_as_json(cls, value: Any) -> Any:
        return value.to_json() if isinstance(value, PlanSnapshot) else value


class SubscriptionDetailResponse(SubscriptionResponse):
    used_traffic: Optional[int] = None  # bytes; None when the panel is unreachable


class SubscriptionListItemResponse(SubscriptionResponse):
    # None once the account is deleted
    user_name: Optional[str] = None


class SubscriptionPageResponse(BaseModel):
    items: list[SubscriptionListItemResponse]
    total: int


class UpdateSubscriptionRequest(BaseModel):
    tag: Optional[str] = Field(
        default=None, max_length=PANEL_TAG_MAX_LENGTH, pattern=PANEL_TAG_PATTERN
    )
    traffic_limit: Optional[int] = Field(default=None, ge=0)
    device_limit: Optional[int] = Field(default=None, ge=0)
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None
    expire_at: Optional[datetime] = None


class DeletedSubscriptionsResponse(BaseModel):
    deleted: int


class UpdateSubscriptionSquadsRequest(BaseModel):
    internal_squads: list[UUID] = Field(default_factory=list)
    external_squad: Optional[UUID] = None


class GrantSubscriptionRequest(BaseModel):
    user_id: int
    plan_id: int
    duration_days: int = Field(ge=1, le=36500)


class ChangeSubscriptionPlanRequest(BaseModel):
    plan_id: int
    duration_days: Optional[int] = Field(default=None, ge=1, le=36500)


class DeviceResponse(BaseModel):
    hwid: str
    platform: Optional[str] = None
    device_model: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    total: int


class PublicPlanPriceResponse(BaseModel):
    currency: Currency
    # 0 only for a free trial plan opened by its code
    price: Decimal = Field(ge=0)
    # the price with the plan's running promotion off it, absent while there is none
    discounted_price: Optional[Decimal] = None


class PublicPlanDurationResponse(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    prices: list[PublicPlanPriceResponse]


class PublicPlanResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    badge: Optional[PlanBadge] = None
    type: PlanType
    traffic_limit_strategy: TrafficLimitStrategy
    traffic_limit: int
    device_limit: int
    is_trial: bool
    order_index: int
    durations: list[PublicPlanDurationResponse]
    discount_percent: int = 0
    discount_ends_at: Optional[datetime] = None


class PublicPlanListResponse(BaseModel):
    items: list[PublicPlanResponse]
    total: int
    anchor_currency: Currency


class OwnSubscriptionResponse(BaseModel):
    id: int
    status: SubscriptionStatus
    is_trial: bool
    expire_at: datetime
    url: str
    effective_traffic_limit: int
    effective_device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    plan_name: str
    plan_id: int
    device_all_reset_at: Optional[datetime] = None
    link_reset_at: Optional[datetime] = None
    used_traffic: Optional[int] = None  # bytes; None when the panel is unreachable
    # vouches for `url` to the cabinet's public deep link page (core/security/connect_signature)
    connect_signature: str

    @classmethod
    def from_dto(
        cls, subscription: SubscriptionDto, *, secret: str, used_traffic: Optional[int] = None
    ) -> "OwnSubscriptionResponse":
        return cls.model_validate(
            {
                **subscription.model_dump(),
                "plan_name": subscription.plan_snapshot.name,
                "plan_id": subscription.plan_snapshot.plan_id,
                "used_traffic": used_traffic,
                "connect_signature": sign_subscription_url(subscription.url, secret),
            }
        )


class OwnSubscriptionListResponse(BaseModel):
    items: list[OwnSubscriptionResponse]
    total: int


class TrialResponse(BaseModel):
    is_available: bool
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None
    duration_days: Optional[int] = None
    # a paid trial is bought through checkout with plan_id, not activated
    is_free: bool = True
    price: Optional[Decimal] = None
    currency: Optional[Currency] = None
    # the one duration in every currency, for the checkout's gateway choice
    prices: list[PublicPlanPriceResponse] = []


class PanelSyncResultResponse(BaseModel):
    direction: PanelSyncDirection
    checked: int
    updated: int
    failed: int
    missing: int
    recreated: int
    imported: int
    deleted: int
    over_limit: int
    finished_at: datetime


class PanelSyncPullRequest(BaseModel):
    adopt_unnamed: bool = True
    respect_subscription_limit: bool = True


class PanelSyncPushRequest(BaseModel):
    recreate_missing: bool = True
    delete_orphans: bool = True


class PanelSyncDirectionStatusResponse(BaseModel):
    direction: PanelSyncDirection
    running: bool
    last: Optional[PanelSyncResultResponse] = None


class PanelSyncStatusResponse(BaseModel):
    from_panel: PanelSyncDirectionStatusResponse
    to_panel: PanelSyncDirectionStatusResponse


class PanelFieldDiffResponse(BaseModel):
    field: str
    shop: str
    panel: str


class PanelSquadResponse(BaseModel):
    uuid: UUID
    name: str
    kind: Literal["internal", "external"]


class PanelSquadListResponse(BaseModel):
    items: list[PanelSquadResponse]
    total: int


class SubscriptionPanelDiffResponse(BaseModel):
    subscription_id: int
    missing_in_panel: bool
    fields: list[PanelFieldDiffResponse]
