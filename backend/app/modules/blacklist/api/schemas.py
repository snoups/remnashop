from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.core.enums import BlacklistKind


class BlacklistResponse(BaseModel):
    telegram_ids: list[int]
    emails: list[str]


class BlacklistEntryRequest(BaseModel):
    kind: BlacklistKind
    value: str


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


class ToggleSourceRequest(BaseModel):
    enabled: bool
