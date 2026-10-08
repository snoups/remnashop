from dataclasses import dataclass
from typing import Literal, Optional

from app.modules.users import UserDto

MergeSide = Literal["source", "target"]


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


@dataclass(frozen=True, kw_only=True)
class MergePreviewDto:
    source: UserDto
    target: UserDto
    conflicts: list[MergeConflictDto]
    source_counts: MergeCountsDto
    fingerprint: str


@dataclass(frozen=True, kw_only=True)
class GetMergePreviewDto:
    target_id: int
    source_id: int


@dataclass(frozen=True, kw_only=True)
class MergeAccountsDto:
    target_id: int
    source_id: int
    choices: dict[str, MergeSide]
    fingerprint: str
