from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.dto import BaseDto, TimestampMixin


class ApiTokenDto(BaseDto, TimestampMixin):
    name: str
    scopes: list[str]
    ip_allowlist: list[str] = []
    created_by_user_id: Optional[int] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class CreateApiTokenDto:
    name: str
    scopes: list[str]
    token_hash: str
    created_by_user_id: Optional[int]
    expires_at: Optional[datetime]
    ip_allowlist: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class IssueApiTokenDto:
    client_ip: str
    name: str
    scopes: list[str]
    expires_in_days: int
    ip_allowlist: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CreatedApiTokenDto:
    token: ApiTokenDto
    secret: str


@dataclass(frozen=True, kw_only=True)
class RevokeApiTokenDto:
    token_id: int
    client_ip: str
