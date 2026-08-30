from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import PromocodeAvailability, PromocodeRewardType


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
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool


class PublicPromocodeResponse(BaseModel):
    # Deliberately excludes allowed_user_ids (would leak other users' ids)
    # and admin-only fields (max_activations, is_reusable) -- a customer
    # only needs to know what they just got.
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
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = Field(default=None, ge=1)
    is_reusable: bool = False


class UpdatePromocodeRequest(BaseModel):
    is_active: Optional[bool] = None
    availability: Optional[PromocodeAvailability] = None
    allowed_user_ids: Optional[list[int]] = None
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = Field(default=None, ge=1)
    is_reusable: Optional[bool] = None


class ActivatePromocodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    target_subscription_id: Optional[int] = None


class GeneratedPromocodeCodeResponse(BaseModel):
    code: str
