from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Optional

from app.core.constants import REMNASHOP_PREFIX, WEB_PREFIX
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Locale, Role
from app.core.utils.time import datetime_now

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


class UserDto(BaseDto, TimestampMixin):
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    login: Optional[str] = None
    password_hash: Optional[str] = None

    name: str
    role: Role = Role.USER
    language: Locale = Locale.EN

    is_blocked: bool = False
    is_trial_available: bool = True

    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None
    personal_discount: int = 0
    purchase_discount: int = 0

    referral_code: Optional[str] = None
    points: Decimal = Decimal(0)

    @property
    def contact_label(self) -> str:
        if self.username:
            return self.username
        if self.telegram_id is not None:
            return str(self.telegram_id)
        return self.email or str(self.id)

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
        return f"[{self.role}:{self.id}:{self.remna_name} ({self.name})]"

    @property
    def remna_name(self) -> str:
        if self.telegram_id is not None:
            return f"{REMNASHOP_PREFIX}{self.telegram_id}"
        return f"{REMNASHOP_PREFIX}{WEB_PREFIX}{self.id}"

    @property
    def remna_description(self) -> str:
        description = f"name: {self.name}"

        if self.username:
            description += f"\nusername: {self.username}"
        if self.email:
            description += f"\nemail: {self.email}"

        return description


@dataclass(frozen=True, kw_only=True)
class CreateUserDto:
    name: str
    role: Role = Role.USER
    language: Locale = Locale.EN
    is_blocked: bool = False
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    login: Optional[str] = None
    password_hash: Optional[str] = None
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None


@dataclass(frozen=True, kw_only=True)
class UpdateUserDto:
    # None = leave unchanged, matching the existing partial-update convention.
    name: Optional[str] = None
    password_hash: Optional[str] = None
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None
    personal_discount: Optional[int] = None
    purchase_discount: Optional[int] = None
    is_trial_available: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class PromoteAdminDto:
    login: str
    password_hash: str
    permission_grants: list[str]
    permission_revokes: list[str]


@dataclass(frozen=True, kw_only=True)
class SetUserPersonalDiscountDto:
    user_id: int
    percent: int


@dataclass(frozen=True, kw_only=True)
class BulkBlockResultDto:
    blocked: int
    added_to_list: int
    skipped: int
