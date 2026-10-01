from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BlacklistResponse(BaseModel):
    telegram_ids: list[int]
    emails: list[str]


class BlacklistSourceResponse(BaseModel):
    id: int
    url: str
    name: Optional[str]
    enabled: bool
    entries_count: int
    last_synced_at: Optional[datetime]
    last_error: Optional[str]


class AddSourceRequest(BaseModel):
    url: str
    name: Optional[str] = None


class UpdateSourceRequest(BaseModel):
    enabled: bool


class BlacklistSourceListResponse(BaseModel):
    items: list[BlacklistSourceResponse]
    total: int
