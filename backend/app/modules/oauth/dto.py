from dataclasses import dataclass
from typing import Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import OAuthProvider


class OAuthIdentityDto(BaseDto, TimestampMixin):
    user_id: int
    provider: OAuthProvider
    external_id: str
    external_login: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class CreateOAuthIdentityDto:
    user_id: int
    provider: OAuthProvider
    external_id: str
    external_login: Optional[str]
