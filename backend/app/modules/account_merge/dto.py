from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import Final, Literal, Optional

from app.core.enums import Locale, Role
from app.modules.users import UserDto

MergeSide = Literal["source", "target"]
# an OAuth conflict is keyed per provider: "oauth:github"
OAUTH_CONFLICT_PREFIX: Final[str] = "oauth:"


class MergeConflictKey(StrEnum):
    TELEGRAM = auto()
    EMAIL = auto()
    LOGIN = auto()
    NAME = auto()
    LANGUAGE = auto()
    PERSONAL_DISCOUNT = auto()
    PURCHASE_DISCOUNT = auto()
    REFERRED_BY = auto()


def oauth_conflict_key(provider: str) -> str:
    return f"{OAUTH_CONFLICT_PREFIX}{provider}"


@dataclass(frozen=True, kw_only=True)
class MergeConflictDto:
    key: str
    source_value: Optional[str]
    target_value: Optional[str]
    # set when a staff side decides it; the admin's choice is ignored then
    forced: Optional[MergeSide] = None


@dataclass(frozen=True, kw_only=True)
class MergeCountsDto:
    subscriptions: int
    transactions: int
    referrals: int
    passkeys: int
    oauth_identities: int


@dataclass(frozen=True, kw_only=True)
class MergeLinksDto:
    source_referrer_id: Optional[int]
    target_referrer_id: Optional[int]
    # provider -> external login or id
    source_oauth: dict[str, str]
    target_oauth: dict[str, str]
    # Referral.created_at, to tell which referrer came first
    source_referred_at: Optional[datetime] = None
    target_referred_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class MergeReferrerCycleDto:
    # keeping this side's referrer would loop through the merged pair, so the merge drops it
    side: MergeSide
    referrer_id: int


@dataclass(frozen=True, kw_only=True)
class MergePreviewDto:
    source: UserDto
    target: UserDto
    conflicts: list[MergeConflictDto]
    referrer_cycles: list[MergeReferrerCycleDto]
    source_counts: MergeCountsDto
    fingerprint: str


@dataclass(frozen=True, kw_only=True)
class GetMergePreviewDto:
    target_id: int
    source_id: int


@dataclass(frozen=True, kw_only=True)
class MergeAccountsDto:
    client_ip: str
    target_id: int
    source_id: int
    choices: dict[str, MergeSide]
    fingerprint: str


@dataclass(frozen=True, kw_only=True)
class MergedUserDto:
    """Every column of the kept account a merge rewrites."""

    telegram_id: Optional[int]
    username: Optional[str]
    email: Optional[str]
    email_undeliverable_at: Optional[datetime]
    login: Optional[str]
    password_hash: Optional[str]
    password_change_required: bool
    name: str
    language: Locale
    personal_discount: int
    personal_discount_promocode_id: Optional[int]
    purchase_discount: int
    purchase_discount_promocode_id: Optional[int]
    role: Role
    permission_grants: Optional[list[str]]
    permission_revokes: Optional[list[str]]
    ip_allowlist: Optional[list[str]]
    notification_channels: Optional[dict[str, list[str]]]
    notifications_seen_at: Optional[datetime]
    notifications_cleared_at: Optional[datetime]
    points: Decimal
    bonus_days: int
    is_trial_available: bool
    is_blocked: bool
    marketing_opt_out: bool
    loyalty_excluded: bool
    rules_accepted_at: Optional[datetime]
