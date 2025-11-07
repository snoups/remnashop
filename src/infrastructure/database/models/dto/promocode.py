from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .plan import PlanSnapshotDto
    from .user import BaseUserDto

from datetime import datetime, timedelta

from pydantic import Field

from src.core.enums import PromocodeAvailability, PromocodeRewardType
from src.core.utils.time import datetime_now

from .base import BaseDto, TrackableDto


class PromocodeDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    code: str = Field(default_factory=lambda: PromocodeDto.generate_code())
    is_active: bool = False

    availability: PromocodeAvailability = PromocodeAvailability.ALL
    reward_type: PromocodeRewardType = PromocodeRewardType.PERSONAL_DISCOUNT
    reward: Optional[int] = 1
    plan: Optional["PlanSnapshotDto"] = None

    lifetime: int = -1
    max_activations: int = -1

    activations: list["PromocodeActivationDto"] = []

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_unlimited(self) -> bool:
        return self.max_activations is None

    @property
    def is_depleted(self) -> bool:
        if self.max_activations is None:
            return False

        return len(self.activations) >= self.max_activations

    @property
    def is_available(self) -> bool:
        return not self.is_expired and not self.is_depleted

    @property
    def expires_at(self) -> Optional[datetime]:
        if self.lifetime is not None and self.created_at is not None:
            return self.created_at + timedelta(days=self.lifetime)
        return None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False

        current_time = datetime_now()
        return current_time > self.expires_at

    @property
    def time_left(self) -> Optional[timedelta]:
        if self.expires_at is None:
            return None

        current_time = datetime_now()
        delta = self.expires_at - current_time
        return delta if delta.total_seconds() > 0 else timedelta(seconds=0)

    @staticmethod
    def generate_code(length: int = 10) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


class PromocodeActivationDto(BaseDto):
    id: Optional[int] = Field(default=None, frozen=True)

    promocode_id: int
    user_telegram_id: int

    activated_at: Optional[datetime] = Field(default=None, frozen=True)

    promocode: Optional["PromocodeDto"] = None
    user: Optional["BaseUserDto"] = None
