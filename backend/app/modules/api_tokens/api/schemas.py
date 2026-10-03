from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApiTokenResponse(BaseModel):
    id: int
    name: str
    scopes: list[str]
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]


class CreateApiTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int = Field(ge=1)


class CreatedApiTokenResponse(BaseModel):
    token: ApiTokenResponse
    secret: str


class DocsOttResponse(BaseModel):
    ott: str


class ApiTokenListResponse(BaseModel):
    items: list[ApiTokenResponse]
    total: int
