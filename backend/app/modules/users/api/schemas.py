import ipaddress
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import LOGIN_PATTERN
from app.core.enums import BlacklistKind
from app.core.security import PASSWORD_MIN_LENGTH, PASSWORD_PATTERN
from app.core.security.permissions import Permission


def _validate_login_charset(value: str) -> str:
    if not LOGIN_PATTERN.match(value):
        raise ValueError(
            "Login may only contain Latin letters, digits, dots, underscores, and hyphens"
        )
    return value


class CurrentUserResponse(BaseModel):
    id: int
    login: Optional[str]
    name: str
    role: str
    effective_permissions: list[Permission]
    password_change_required: bool


class AdminResponse(BaseModel):
    id: int
    login: Optional[str]
    name: str
    role: str
    telegram_id: Optional[int]
    username: Optional[str]
    email: Optional[str]
    language: str
    is_blocked: bool
    personal_discount: int
    purchase_discount: int
    points: Decimal
    bonus_days: int
    is_trial_available: bool
    created_at: Optional[datetime]
    permission_grants: list[Permission]
    permission_revokes: list[Permission]
    role_permissions: list[Permission]
    effective_permissions: list[Permission]


class AdminWithPasswordResponse(BaseModel):
    admin: AdminResponse
    password: str


class AdminPromoteResponse(BaseModel):
    admin: AdminResponse
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    role: str
    telegram_id: Optional[int]
    username: Optional[str]
    email: Optional[str]
    login: Optional[str]
    language: str
    is_blocked: bool
    personal_discount: int
    purchase_discount: int
    referral_code: Optional[str]
    points: Decimal
    bonus_days: int
    is_trial_available: bool
    created_at: Optional[datetime]
    deleted_at: Optional[datetime] = None

    @field_validator("role", "language", mode="before")
    @classmethod
    def _enum_as_name(cls, value: object) -> str:
        # Role's value is its rank; the API speaks its name
        return str(value)


class BlacklistOriginResponse(BaseModel):
    source_id: Optional[int]
    source_name: Optional[str]


class BlacklistHitResponse(BaseModel):
    kind: BlacklistKind
    value: str
    origins: list[BlacklistOriginResponse]


class BlacklistMatchResponse(BaseModel):
    user: UserResponse
    hits: list[BlacklistHitResponse]


class BlacklistMatchPageResponse(BaseModel):
    items: list[BlacklistMatchResponse]
    total: int
    all_total: int
    manual_total: int
    lists_total: int


class UserListItemResponse(UserResponse):
    active_subscriptions: int
    limited_subscriptions: int
    expired_subscriptions: int


class UserPageResponse(BaseModel):
    items: list[UserListItemResponse]
    total: int


class UserListStatsResponse(BaseModel):
    total: int
    new: int
    subscribed: int
    blocked: int
    new_previous: int
    total_growth: int


class CreateAdminRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    permission_grants: list[Permission] = Field(default_factory=list)
    permission_revokes: list[Permission] = Field(default_factory=list)

    _validate_login = field_validator("login")(_validate_login_charset)


class PromoteAdminRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    login: Optional[str] = Field(default=None, min_length=1, max_length=64)
    permission_grants: list[Permission] = Field(default_factory=list)
    permission_revokes: list[Permission] = Field(default_factory=list)

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: Optional[str]) -> Optional[str]:
        return _validate_login_charset(value) if value is not None else value

    @model_validator(mode="after")
    def validate_exactly_one_identifier(self) -> "PromoteAdminRequest":
        identifiers = (self.user_id is not None, bool(self.email), bool(self.telegram_username))
        if sum(identifiers) != 1:
            raise ValueError("Provide exactly one of user_id, email or telegram_username")
        return self


class UpdateAdminRequest(BaseModel):
    # None means "field omitted, leave unchanged"; an explicit [] clears the overrides.
    permission_grants: Optional[list[Permission]] = None
    permission_revokes: Optional[list[Permission]] = None


class UpdateOwnProfileRequest(BaseModel):
    # None means "field omitted, leave unchanged", matching UpdateAdminRequest's convention.
    name: Optional[str] = Field(default=None, min_length=1)
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not PASSWORD_PATTERN.match(value):
            raise ValueError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and contain "
                "an uppercase letter, a lowercase letter, and a digit"
            )
        return value

    @model_validator(mode="after")
    def validate_current_password_present(self) -> "UpdateOwnProfileRequest":
        if self.new_password is not None and not self.current_password:
            raise ValueError("current_password is required to set a new password")
        return self


class UpdateSecurityRequest(BaseModel):
    ip_allowlist: list[str]

    @field_validator("ip_allowlist")
    @classmethod
    def validate_entries(cls, value: list[str]) -> list[str]:
        for entry in value:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError as error:
                raise ValueError(f"Invalid IP or CIDR: {entry}") from error
        return value


class SetDiscountRequest(BaseModel):
    personal_discount: Optional[int] = Field(None, ge=0, le=100)
    purchase_discount: Optional[int] = Field(None, ge=0, le=100)


class SecurityResponse(BaseModel):
    ip_allowlist: list[str]
    # the address this request came from, as the allowlist check sees it
    client_ip: str


class UnblockAllResponse(BaseModel):
    unblocked: int


class AdminListResponse(BaseModel):
    items: list[AdminResponse]
    total: int
