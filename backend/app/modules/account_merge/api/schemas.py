from typing import Literal, Optional

from pydantic import BaseModel

from app.modules.users import UserResponse


class MergeConflictResponse(BaseModel):
    key: str
    source_value: Optional[str]
    target_value: Optional[str]
    forced: Optional[Literal["source", "target"]]


class MergeReferrerCycleResponse(BaseModel):
    side: Literal["source", "target"]
    referrer_id: int


class MergeCountsResponse(BaseModel):
    subscriptions: int
    transactions: int
    referrals: int
    passkeys: int
    oauth_identities: int


class MergePreviewResponse(BaseModel):
    source: UserResponse
    target: UserResponse
    conflicts: list[MergeConflictResponse]
    referrer_cycles: list[MergeReferrerCycleResponse]
    source_counts: MergeCountsResponse
    fingerprint: str


class MergeAccountsRequest(BaseModel):
    source_id: int
    fingerprint: str
    choices: dict[str, Literal["source", "target"]] = {}
