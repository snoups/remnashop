from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import Currency, PromocodeAvailability, PromocodeRewardType
from app.core.utils.time import range_start_utc


class PromocodeResponse(BaseModel):
    id: int
    code: str
    is_active: bool
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability
    allowed_user_ids: list[int]
    allowed_plan_ids: list[int]
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool
    created_at: Optional[datetime] = None


class PublicPromocodeResponse(BaseModel):
    # no allowed_user_ids (other users' ids) and no admin-only fields
    # (max_activations, is_reusable)
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None


class CreatePromocodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability = PromocodeAvailability.ALL
    allowed_user_ids: list[int] = Field(default_factory=list)
    allowed_plan_ids: list[int] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = Field(default=None, ge=1)
    is_reusable: bool = False

    @field_validator("expires_at")
    @classmethod
    def _expires_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        # a naive time is taken as UTC
        return range_start_utc(value)


class UpdatePromocodeRequest(BaseModel):
    is_active: Optional[bool] = None
    availability: Optional[PromocodeAvailability] = None
    allowed_user_ids: Optional[list[int]] = None
    allowed_plan_ids: Optional[list[int]] = None
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = Field(default=None, ge=1)
    is_reusable: Optional[bool] = None

    @field_validator("expires_at")
    @classmethod
    def _expires_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        # a naive time is taken as UTC
        return range_start_utc(value)


class ActivatePromocodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    target_subscription_id: Optional[int] = None


class GeneratedPromocodeCodeResponse(BaseModel):
    code: str


class UserPromocodeActivationResponse(BaseModel):
    activation_id: int
    promocode_id: int
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_duration_days: Optional[int] = None
    activated_at: datetime


class PromocodeSummaryResponse(BaseModel):
    total_count: int
    active_count: int
    activations_count: int
    activated_users_count: int
    activations_by_promocode: dict[int, int]
    granted_days: int
    granted_subscriptions_count: int
    report_currency: Currency
    discount_amount: Decimal
    discounted_orders_count: int


class PromocodeActivatedUserResponse(BaseModel):
    activation_id: int
    user_id: int
    name: str
    subscription_id: Optional[int] = None
    activated_at: datetime


class PromocodePageResponse(BaseModel):
    items: list[PromocodeResponse]
    total: int


class PromocodeActivatedUserPageResponse(BaseModel):
    items: list[PromocodeActivatedUserResponse]
    total: int


class UserPromocodeActivationListResponse(BaseModel):
    items: list[UserPromocodeActivationResponse]
    total: int
