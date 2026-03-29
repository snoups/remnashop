from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.core.enums import PromocodeRewardType

from .base import BaseDto, TimestampMixin, TrackableMixin
from .user import UserDto


@dataclass(kw_only=True)
class PromocodeDto(BaseDto, TrackableMixin, TimestampMixin):
    code: str
    is_active: bool = True

    reward_type: PromocodeRewardType
    reward: Optional[int] = None
    plan: Optional[dict[str, Any]] = None
    lifetime: Optional[int] = None
    max_activations: Optional[int] = None


@dataclass(kw_only=True)
class PromocodeActivationDto(BaseDto):
    promocode_id: int
    user_telegram_id: int
    activated_at: Optional[datetime] = None


@dataclass(kw_only=True)
class ActivatePromocodeResultDto:
    user: UserDto
    code: str
    promocode_type: PromocodeRewardType
    reward: int
    applied_discount: int
    has_activation_limit: bool
    remaining_activations: Optional[int] = None
    has_lifetime_limit: bool = False
    remaining_lifetime_days: Optional[int] = None
