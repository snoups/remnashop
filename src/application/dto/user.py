from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Self

from aiogram.types import User as AiogramUser

from src.core.constants import REMNASHOP_PREFIX
from src.core.enums import Locale, Role
from src.core.utils.time import datetime_now

from .base import BaseDto, TimestampMixin, TrackableMixin


@dataclass(kw_only=True)
class TempUserDto:
    telegram_id: int
    name: str
    role: Role = Role.USER
    language: Locale = Locale.EN

    @classmethod
    def from_aiogram(cls, aiogram_user: AiogramUser) -> Self:
        return cls(
            telegram_id=aiogram_user.id,
            name=aiogram_user.full_name,
        )

    @classmethod
    def as_temp_owner(cls, telegram_id: int) -> Self:
        return cls(telegram_id=telegram_id, name="OWNER", role=Role.OWNER)


@dataclass(kw_only=True)
class UserDto(BaseDto, TrackableMixin, TimestampMixin):
    telegram_id: int

    login: Optional[str] = None
    email: Optional[str] = None
    password_hash: Optional[str] = None
    is_email_verified: bool = False
    pending_email: Optional[str] = None
    email_verification_code_hash: Optional[str] = None
    email_verification_expires_at: Optional[datetime] = None

    username: Optional[str] = None
    referral_code: str = ""

    name: str
    role: Role = Role.USER
    language: Locale = Locale.EN

    personal_discount: int = 0
    purchase_discount: int = 0
    points: int = 0

    is_blocked: bool = False
    is_bot_blocked: bool = False
    is_rules_accepted: bool = False
    is_trial_available: bool = True

    @property
    def is_privileged(self) -> bool:
        return self.role.includes(Role.ADMIN)

    @property
    def is_owner(self) -> bool:
        return self.role.includes(Role.OWNER)

    @property
    def age_days(self) -> Optional[int]:
        if self.created_at is None:
            return None

        return (datetime_now() - self.created_at).days

    @property
    def log(self) -> str:
        return f"[{self.role}:{self.telegram_id} ({self.name})]"

    @property
    def remna_name(self) -> str:  # NOTE: DONT USE FOR GET USER!
        return f"{REMNASHOP_PREFIX}{self.telegram_id}"

    @property
    def remna_description(self) -> str:
        description = f"name: {self.name}"

        if self.username:
            description += f"\nusername: {self.username}"
        if self.email:
            description += f"\nemail: {self.email}"

        return description
