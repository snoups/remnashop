from datetime import datetime
from typing import Any, Final, Optional

from app.core.dto import BaseDto
from app.core.events import EventCategory

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


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
