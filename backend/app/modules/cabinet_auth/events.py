from dataclasses import dataclass
from typing import ClassVar

from app.core.events import BaseEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class EmailCodeAttemptsExhaustedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    email_hash: str
