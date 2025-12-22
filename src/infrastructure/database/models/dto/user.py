from datetime import datetime
from typing import Optional

from pydantic import Field, PrivateAttr

from src.core.enums import Locale, UserRole
from src.core.utils.time import datetime_now

from .base import TrackableDto


class UserDto(TrackableDto):
    _id: Optional[int] = PrivateAttr(Field(default=None, frozen=True))
    telegram_id: int
    username: Optional[str] = None
    referral_code: str = ""

    name: str
    role: UserRole = UserRole.USER
    language: Locale = Locale.EN

    personal_discount: int = 0
    purchase_discount: int = 0
    points: int = 0

    is_blocked: bool = False
    is_bot_blocked: bool = False
    is_rules_accepted: bool = False

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

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
