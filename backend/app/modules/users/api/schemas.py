from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import LOGIN_PATTERN
from app.core.enums import BlacklistKind, Locale
from app.core.security import PASSWORD_MIN_LENGTH, PASSWORD_PATTERN
from app.core.security.permissions import Permission
from app.core.utils.http import validate_ip_allowlist
from app.modules.users.schemas import UserListItemResponse, UserResponse


def _validate_login_charset(value: str) -> str:
    if not LOGIN_PATTERN.fullmatch(value):
        raise ValueError(
            "Login may only contain Latin letters, digits, dots, underscores, and hyphens"
        )
    return value


class AdminResponse(UserResponse):
    permission_grants: list[Permission]
    permission_revokes: list[Permission]
    role_permissions: list[Permission]
    effective_permissions: list[Permission]

    @field_validator("permission_grants", "permission_revokes", mode="before")
    @classmethod
    def _known_permissions(cls, value: Optional[list[str]]) -> list[str]:
        # a stored override can outlive its permission
        return [p for p in value or [] if p in Permission]


class AdminWithPasswordResponse(BaseModel):
    admin: AdminResponse
    password: str


class AdminPromoteResponse(BaseModel):
    admin: AdminResponse
    password: Optional[str] = None


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


class RegistrationSnapshotResponse(BaseModel):
    source: str
    start_payload: Optional[str]
    telegram_language_code: Optional[str]
    telegram_is_premium: Optional[bool]
    ip_address: Optional[str]
    user_agent: Optional[str]
    browser: Optional[str]
    created_at: datetime


class UserRegistrationResponse(BaseModel):
    # null: the account predates registration snapshots
    registration: Optional[RegistrationSnapshotResponse]


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
    permission_grants: list[Permission] = Field(default_factory=list)
    permission_revokes: list[Permission] = Field(default_factory=list)

    _validate_login = field_validator("login")(_validate_login_charset)


class PromoteAdminRequest(BaseModel):
    user_id: int
    login: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: Optional[str]) -> Optional[str]:
        return _validate_login_charset(value) if value is not None else value


class UpdateAdminRequest(BaseModel):
    # None means "field omitted, leave unchanged"; an explicit [] clears the overrides.
    permission_grants: Optional[list[Permission]] = None
    permission_revokes: Optional[list[Permission]] = None


class UpdateOwnProfileRequest(BaseModel):
    # None = field omitted, leave unchanged
    name: Optional[str] = Field(default=None, min_length=1)
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    language: Optional[Locale] = None

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

    _validate_ip_allowlist = field_validator("ip_allowlist")(validate_ip_allowlist)


class SetDiscountRequest(BaseModel):
    personal_discount: Optional[int] = Field(None, ge=0, le=100)
    purchase_discount: Optional[int] = Field(None, ge=0, le=100)


class BindTelegramRequest(BaseModel):
    telegram_id: int = Field(gt=0, le=9_223_372_036_854_775_807)


class SecurityResponse(BaseModel):
    ip_allowlist: list[str]
    # the address this request came from, as the allowlist check sees it
    client_ip: str

    @field_validator("ip_allowlist", mode="before")
    @classmethod
    def _unset_as_empty(cls, value: Optional[list[str]]) -> list[str]:
        return value or []


class UnblockBlacklistMatchesResponse(BaseModel):
    unblocked: int


class AdminListResponse(BaseModel):
    items: list[AdminResponse]
    total: int
    customer_sign_in_ids: list[int]
