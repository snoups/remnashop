from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from app.core.constants import DEFAULT_PAGE_SIZE, REMNASHOP_PREFIX, WEB_PREFIX
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    AdLinkChannel,
    BlacklistKind,
    CabinetSignInMethod,
    Locale,
    RegistrationSource,
    Role,
)
from app.core.security.permissions import Permission
from app.core.utils.http import describe_user_agent
from app.core.utils.time import datetime_now
from app.modules.blacklist import BlacklistOriginDto

UserSort = Literal["created_at", "points", "discount", "name", "channels", "subscriptions"]
# exclude: live users only (the default); include: both; only: soft-deleted ones
DeletedFilter = Literal["exclude", "include", "only"]


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
    password_change_required: bool = False

    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None
    personal_discount: int = 0
    purchase_discount: int = 0
    personal_discount_promocode_id: Optional[int] = None
    purchase_discount_promocode_id: Optional[int] = None
    loyalty_discount: int = 0
    loyalty_excluded: bool = False
    marketing_opt_out: bool = False
    is_bot_blocked: bool = False
    email_undeliverable_at: Optional[datetime] = None
    rules_accepted_at: Optional[datetime] = None

    referral_code: Optional[str] = None
    points: Decimal = Decimal(0)
    bonus_days: int = 0
    notifications_seen_at: Optional[datetime] = None
    notifications_cleared_at: Optional[datetime] = None
    notification_channels: Optional[dict[str, list[str]]] = None
    deleted_at: Optional[datetime] = None

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


class UserListItemDto(UserDto):
    active_subscriptions: int = 0
    limited_subscriptions: int = 0
    expired_subscriptions: int = 0


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
    password_change_required: bool = False
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None


@dataclass(frozen=True, kw_only=True)
class UserLoyaltyStateDto:
    user_id: int
    discount: int
    excluded: bool


@dataclass(frozen=True, kw_only=True)
class UpdateUserDto:
    # None = leave unchanged.
    name: Optional[str] = None
    password_hash: Optional[str] = None
    password_change_required: Optional[bool] = None
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    ip_allowlist: Optional[list[str]] = None
    personal_discount: Optional[int] = None
    purchase_discount: Optional[int] = None
    # written together with its discount above, so any other writer clears it
    personal_discount_promocode_id: Optional[int] = None
    purchase_discount_promocode_id: Optional[int] = None
    is_trial_available: Optional[bool] = None
    loyalty_excluded: Optional[bool] = None
    language: Optional[Locale] = None


@dataclass(frozen=True, kw_only=True)
class PromoteAdminDto:
    login: str
    password_hash: str
    password_change_required: bool
    permission_grants: list[str]
    permission_revokes: list[str]


@dataclass(frozen=True, kw_only=True)
class SetUserDiscountDto:
    user_id: int
    client_ip: str
    personal_discount: Optional[int] = None
    purchase_discount: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class BindTelegramDto:
    user_id: int
    telegram_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class UserListStatsDto:
    total: int
    new: int
    subscribed: int
    blocked: int
    # registrations in the window just before `new`'s
    new_previous: int
    # registrations within TOTAL_GROWTH_WINDOW
    total_growth: int


@dataclass(frozen=True, kw_only=True)
class CreateAdminDto:
    login: str
    name: str
    client_ip: str
    permission_grants: list[Permission] = field(default_factory=list)
    permission_revokes: list[Permission] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class DeleteAdminDto:
    user_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class DeleteUserDto:
    user_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class DemoteAdminDto:
    user_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class GetUserListStatsDto:
    include_staff: bool = False


BlacklistMatchOrigin = Literal["manual", "lists"]


@dataclass(frozen=True, kw_only=True)
class ListBlacklistMatchesDto:
    search: Optional[str] = None
    # unset = every origin
    origin: Optional[BlacklistMatchOrigin] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class BlacklistHitDto:
    kind: BlacklistKind
    value: str
    origins: list[BlacklistOriginDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistMatchDto:
    user: UserDto
    hits: list[BlacklistHitDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistMatchPageDto:
    items: list[BlacklistMatchDto]
    total: int
    all_total: int
    manual_total: int
    lists_total: int


@dataclass(frozen=True, kw_only=True)
class ListUsersDto:
    search: Optional[str] = None
    role: Optional[Role] = None
    is_blocked: Optional[bool] = None
    include_staff: bool = False
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    has_discount: Optional[bool] = None
    has_subscription: Optional[bool] = None
    is_trial_available: Optional[bool] = None
    # blocked users whose telegram id/email is on that blacklist origin
    blocked_by: Optional[BlacklistMatchOrigin] = None
    deleted: DeletedFilter = "exclude"
    sort: UserSort = "created_at"
    descending: bool = True
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class PromoteToAdminDto:
    client_ip: str
    user_id: Optional[int] = None
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    login: Optional[str] = None
    permission_grants: list[Permission] = field(default_factory=list)
    permission_revokes: list[Permission] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class RegistrationSnapshotDto:
    source: RegistrationSource
    start_payload: Optional[str] = None
    telegram_language_code: Optional[str] = None
    telegram_is_premium: Optional[bool] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class UserRegistrationDto(BaseDto):
    source: RegistrationSource
    start_payload: Optional[str] = None
    telegram_language_code: Optional[str] = None
    telegram_is_premium: Optional[bool] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    @property
    def browser(self) -> Optional[str]:
        return describe_user_agent(self.user_agent) if self.user_agent else None


@dataclass(frozen=True, kw_only=True)
class RegisterTelegramUserDto:
    telegram_id: int
    name: str
    username: Optional[str] = None
    language: Locale
    # True when `language` is the user's own active Telegram language, not the
    # deployment default; only then may it overwrite a stored one
    sync_language: bool = False
    # raw deep-link payloads; advertising and referrals resolve them
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None
    channel: AdLinkChannel = AdLinkChannel.BOT
    snapshot: Optional[RegistrationSnapshotDto] = None


@dataclass(frozen=True, kw_only=True)
class RegisterCabinetUserDto:
    name: str
    language: Locale
    method: CabinetSignInMethod
    email: Optional[str] = None
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None
    snapshot: Optional[RegistrationSnapshotDto] = None


@dataclass(frozen=True, kw_only=True)
class UpdateAdminDto:
    user_id: int
    client_ip: str
    # None means "field omitted, leave unchanged"; an explicit [] clears the overrides.
    permission_grants: Optional[list[Permission]] = None
    permission_revokes: Optional[list[Permission]] = None


@dataclass(frozen=True, kw_only=True)
class UpdateOwnProfileDto:
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    language: Optional[Locale] = None
    # kept signed in when the password changes
    current_session_id: Optional[int] = None
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class UpdateSecuritySettingsDto:
    ip_allowlist: list[str]
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class SetBotBlockedDto:
    telegram_id: int
    blocked: bool


@dataclass(frozen=True, kw_only=True)
class SetMarketingOptOutDto:
    opted_out: bool


@dataclass(frozen=True, kw_only=True)
class AdminWithPasswordDto:
    admin: UserDto
    # shown once; None when a promoted user keeps the password they already had
    password: Optional[str]


@dataclass(frozen=True, kw_only=True)
class BlockUserDto:
    user_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class ClearEmailUndeliverableDto:
    user_id: int
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class UnblockUserDto:
    user_id: int
    client_ip: str
