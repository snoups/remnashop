from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.security.permissions import Permission


class ApiTokenDto(BaseDto, TimestampMixin):
    name: str
    permissions: list[Permission]
    created_by_user_id: Optional[int] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class CreateApiTokenDto:
    name: str
    permissions: list[Permission]
    token_hash: str
    created_by_user_id: Optional[int]
    expires_at: Optional[datetime]


@dataclass(frozen=True, kw_only=True)
class IssueApiTokenDto:
    name: str
    permissions: list[Permission]
    expires_in_days: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class CreatedApiTokenDto:
    token: ApiTokenDto
    secret: str
