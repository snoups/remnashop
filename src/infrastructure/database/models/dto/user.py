from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .subscription import BaseSubscriptionDto

from datetime import datetime

from pydantic import Field

from src.core.constants import REMNASHOP_PREFIX
from src.core.enums import Locale, UserRole
from src.core.utils.time import datetime_now

from .base import TrackableDto


class BaseUserDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
    telegram_id: int
    username: Optional[str] = None

    name: str
    role: UserRole = UserRole.USER
    language: Locale

    personal_discount: int = 0
    purchase_discount: int = 0

    is_blocked: bool = False
    is_bot_blocked: bool = False

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def remna_name(self) -> str:  # NOTE: DONT USE FOR GET!
        return f"{REMNASHOP_PREFIX}{self.telegram_id}"

    @property
    def remna_description(self) -> str:
        return f"name: {self.name}\nusername: {self.username or ''}"

    @property
    def is_dev(self) -> bool:
        return self.role == UserRole.DEV

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_privileged(self) -> bool:
        return self.is_admin or self.is_dev

    @property
    def age_days(self) -> Optional[int]:
        if self.created_at is None:
            return None

        return (datetime_now() - self.created_at).days


class UserDto(BaseUserDto):
    current_subscription: Optional["BaseSubscriptionDto"] = None

    @property
    def has_subscription(self) -> bool:
        return bool(self.current_subscription)
