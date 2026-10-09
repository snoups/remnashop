from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.utils.http import validate_ip_allowlist


class ApiTokenResponse(BaseModel):
    id: int
    name: str
    scopes: list[str]
    ip_allowlist: list[str]
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]


class CreateApiTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int = Field(ge=1, le=3650)
    ip_allowlist: list[str] = []

    _validate_ip_allowlist = field_validator("ip_allowlist")(validate_ip_allowlist)


class CreatedApiTokenResponse(BaseModel):
    token: ApiTokenResponse
    secret: str


class DocsOttResponse(BaseModel):
    ott: str


class ApiTokenListResponse(BaseModel):
    items: list[ApiTokenResponse]
    total: int
