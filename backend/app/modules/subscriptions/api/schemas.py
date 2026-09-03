from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import AddOnType, Currency, SubscriptionStatus


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


class SubscriptionPageResponse(BaseModel):
    items: list[SubscriptionResponse]
    total: int


class UpdateSubscriptionRequest(BaseModel):
    tag: Optional[str] = Field(default=None, max_length=32)
    traffic_limit: Optional[int] = Field(default=None, ge=0)
    device_limit: Optional[int] = Field(default=None, ge=0)
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None


class UpdateSubscriptionSquadsRequest(BaseModel):
    internal_squads: list[UUID] = Field(default_factory=list)
    external_squad: Optional[UUID] = None


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
    prices: list[AddOnPriceItem]


class CreateAddOnRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AddOnType
    amount: int = Field(gt=0)


class UpdateAddOnRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    type: Optional[AddOnType] = None
    amount: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None


class SetAddOnPricesRequest(BaseModel):
    prices: list[AddOnPriceItem]


class ReorderAddOnsRequest(BaseModel):
    addon_ids: list[int]
