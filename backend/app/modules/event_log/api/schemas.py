from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class EventLogEntryResponse(BaseModel):
    id: int
    category: str
    event_type: str
    occurred_at: datetime
    actor_id: Optional[int]
    actor_login: Optional[str]
    actor_name: Optional[str]
    ip_address: Optional[str]
    payload: dict[str, Any]


class EventLogPageResponse(BaseModel):
    items: list[EventLogEntryResponse]
    total: int


class NotificationsResponse(BaseModel):
    items: list[EventLogEntryResponse]
    total: int
    unread_count: int
