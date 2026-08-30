from dataclasses import dataclass
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
    # Set only by get_current_actor for a synthetic, non-persisted actor
    # built from an ApiToken match -- never true for a real User row.
    is_api_token: bool = False

    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None

    @property
    def contact_label(self) -> str:
        if self.username:
            return self.username
        if self.telegram_id is not None:
            return str(self.telegram_id)
        return self.email or str(self.id)

    @property
    def is_privileged(self) -> bool:
        return self.role.includes(Role.ADMIN) or self.is_api_token

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


@dataclass(frozen=True, kw_only=True)
class PromoteAdminDto:
    login: str
    password_hash: str
    permission_grants: list[str]
    permission_revokes: list[str]
