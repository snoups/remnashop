from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PasskeyResponse(BaseModel):
    id: int
    name: str
    device_type: str
    backed_up: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class VerifyPasskeyRegistrationRequest(BaseModel):
    credential: dict[str, Any]
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class RenamePasskeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class VerifyPasskeyAuthenticationRequest(BaseModel):
    credential: dict[str, Any]


class PasskeyListResponse(BaseModel):
    items: list[PasskeyResponse]
    total: int
