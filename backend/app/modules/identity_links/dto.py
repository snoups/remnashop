from dataclasses import dataclass, field
from enum import auto
from typing import Final, Literal, Optional

from app.core.enums import OAuthProvider, UpperStrEnum
from app.modules.cabinet_auth import TelegramProfileDto
from app.modules.oauth import CABINET_ONLY_PROVIDERS, OAuthProfile
from app.modules.users import UserDto


class IdentityKind(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()
    GOOGLE = auto()
    YANDEX = auto()

    @classmethod
    def _missing_(cls, value: object) -> Optional["IdentityKind"]:
        # path params arrive lowercase ("telegram")
        return cls.__members__.get(value.upper()) if isinstance(value, str) else None


def identity_kind_for(provider: OAuthProvider) -> IdentityKind:
    return IdentityKind(provider.value)


# no dashboard sign-in behind them: the only methods staff change from the cabinet
STAFF_EDITABLE_KINDS: Final[frozenset[IdentityKind]] = frozenset(
    identity_kind_for(provider) for provider in CABINET_ONLY_PROVIDERS
)


def can_edit_identity(user: UserDto, kind: IdentityKind) -> bool:
    return not user.is_privileged or kind in STAFF_EDITABLE_KINDS


@dataclass(frozen=True, kw_only=True)
class IdentityClaimDto:
    # a sign-in just proven by the customer; only the field matching `kind` is set
    kind: IdentityKind
    telegram: Optional[TelegramProfileDto] = None
    email: Optional[str] = None
    oauth: Optional[OAuthProfile] = None


@dataclass(frozen=True, kw_only=True)
class IdentityDto:
    kind: IdentityKind
    linked: bool
    label: Optional[str]
    # staff: Telegram and email are the dashboard's
    editable: bool = True


@dataclass(frozen=True, kw_only=True)
class MergePreviewDto:
    subscriptions: int
    transactions: int
    referrals: int
    identities: list[IdentityDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class LinkResultDto:
    status: Literal["linked", "already_linked", "merge_required"]
    merge_token: Optional[str] = None
    expires_in: Optional[int] = None
    other: Optional[MergePreviewDto] = None


@dataclass(frozen=True, kw_only=True)
class MergeTicketDto:
    user_id: int
    other_user_id: int
    claim: IdentityClaimDto
