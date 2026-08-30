from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.security.permissions import Permission


class ApiTokenResponse(BaseModel):
    id: int
    name: str
    permissions: list[Permission]
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]


class CreateApiTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    permissions: list[Permission]
    expires_in_days: Optional[int] = Field(default=None, ge=1)


class CreatedApiTokenResponse(BaseModel):
    token: ApiTokenResponse
    secret: str
