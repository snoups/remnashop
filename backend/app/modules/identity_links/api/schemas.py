from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.enums import Locale
from app.modules.identity_links.dto import IdentityKind

_EMAIL_PATTERN = r'^[^@\s(),<>;:"]+@[^@\s(),<>;:"]+$'


class LinkEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    locale: Locale = Locale.EN


class LinkEmailVerifyRequest(BaseModel):
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    code: str = Field(pattern=r"^\d{6}$")


class IdentityResponse(BaseModel):
    kind: IdentityKind
    linked: bool
    label: Optional[str]


class IdentitiesResponse(BaseModel):
    items: list[IdentityResponse]


class MergeRequest(BaseModel):
    merge_token: str = Field(min_length=1, max_length=128)


class MergePreviewResponse(BaseModel):
    subscriptions: int
    transactions: int
    referrals: int
    identities: list[IdentityResponse]


# the answer of every link flow (email, bot, OAuth)
class LinkResultResponse(BaseModel):
    status: Literal["linked", "already_linked", "merge_required"]
    merge_token: Optional[str] = None
    expires_in: Optional[int] = None
    other: Optional[MergePreviewResponse] = None
