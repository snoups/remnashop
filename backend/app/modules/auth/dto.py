from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import OAuthProvider


@dataclass(frozen=True, kw_only=True)
class AuthStatusDto:
    owner_exists: bool
    oauth_providers: dict[OAuthProvider, bool]
    oidc_display_name: Optional[str]
    password_login_enabled: bool
    is_passkey_login_enabled: bool


class SessionDto(BaseDto, TimestampMixin):
    user_id: int
    ip_address: str
    user_agent: Optional[str] = None
    last_used_at: datetime
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreateSessionDto:
    user_id: int
    refresh_token_hash: str
    ip_address: str
    user_agent: Optional[str]
    expires_at: datetime
