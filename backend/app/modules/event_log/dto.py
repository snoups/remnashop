from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Optional

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.dto import BaseDto
from app.core.events import EventCategory

NOTIFICATIONS_LIMIT: Final[int] = 20


class EventLogEntryDto(BaseDto):
    category: EventCategory
    event_type: str
    occurred_at: datetime

    actor_id: Optional[int] = None
    actor_login: Optional[str] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None

    ip_address: Optional[str] = None

    payload: dict[str, Any] = {}

    outbox_id: Optional[int] = None
    target_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class NotificationsDto:
    items: list[EventLogEntryDto]
    unread_count: int


@dataclass(frozen=True, kw_only=True)
class ListEventLogDto:
    category: Optional[EventCategory] = None
    actor_id: Optional[int] = None
    target_id: Optional[int] = None
    event_type: Optional[str] = None
    search: Optional[str] = None
    occurred_from: Optional[datetime] = None
    occurred_to: Optional[datetime] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
