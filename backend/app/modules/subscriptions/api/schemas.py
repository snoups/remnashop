from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import AddOnType, Currency, PlanType, SubscriptionStatus
from app.modules.subscriptions.dto import PlanSnapshot, SubscriptionDto


class AddOnEntitlementItem(BaseModel):
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
    url: str
    plan_snapshot: dict[str, Any]
    device_single_reset_at: Optional[datetime] = None
    device_all_reset_at: Optional[datetime] = None
    link_reset_at: Optional[datetime] = None
    addon_entitlements: list[AddOnEntitlementItem]

    @field_validator("plan_snapshot", mode="before")
    @classmethod
    def _snapshot_as_json(cls, value: Any) -> Any:
        return value.to_json() if isinstance(value, PlanSnapshot) else value


class SubscriptionPageResponse(BaseModel):
    items: list[SubscriptionResponse]
    total: int


class UpdateSubscriptionRequest(BaseModel):
    tag: Optional[str] = Field(default=None, max_length=32)
    traffic_limit: Optional[int] = Field(default=None, ge=0)
    device_limit: Optional[int] = Field(default=None, ge=0)
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None
    expire_at: Optional[datetime] = None


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


class DeviceItem(BaseModel):
    hwid: str
    platform: Optional[str] = None
    device_model: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class DeviceListResponse(BaseModel):
    items: list[DeviceItem]
    total: int


class PublicPlanPriceItem(BaseModel):
    currency: Currency
    price: Decimal = Field(gt=0)


class PublicPlanDurationItem(BaseModel):
    days: int = Field(gt=0)
    order_index: int = 0
    prices: list[PublicPlanPriceItem]


class PublicPlanResponse(BaseModel):
    id: int
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
    link_reset_at: Optional[datetime] = None

    @classmethod
    def from_dto(cls, subscription: SubscriptionDto) -> "OwnSubscriptionResponse":
        return cls.model_validate(
            {**subscription.model_dump(), "plan_name": subscription.plan_snapshot.name}
        )


class OwnSubscriptionListResponse(BaseModel):
    items: list[OwnSubscriptionResponse]
    total: int


class TrialResponse(BaseModel):
    is_available: bool
    plan_name: Optional[str] = None
    duration_days: Optional[int] = None
