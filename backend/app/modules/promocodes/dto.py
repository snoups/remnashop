from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import PromocodeAvailability, PromocodeRewardType


class PromocodeDto(BaseDto, TimestampMixin):
    code: str
    is_active: bool
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability = PromocodeAvailability.ALL
    allowed_user_ids: list[int] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool = False


class PromocodeActivationDto(BaseDto):
    promocode_id: int
    user_id: int
    subscription_id: Optional[int] = None
    activated_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreatePromocodeDto:
    code: str
    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    reward_addon_id: Optional[int] = None
    reward_plan_id: Optional[int] = None
    reward_duration_days: Optional[int] = None
    availability: PromocodeAvailability = PromocodeAvailability.ALL
    allowed_user_ids: list[int] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: bool = False


@dataclass(frozen=True, kw_only=True)
class UpdatePromocodeDto:
    promocode_id: int
    is_active: Optional[bool] = None
    availability: Optional[PromocodeAvailability] = None
    allowed_user_ids: Optional[list[int]] = None
    expires_at: Optional[datetime] = None
    max_activations: Optional[int] = None
    is_reusable: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class ActivatePromocodeDto:
    code: str
    target_subscription_id: Optional[int] = None
