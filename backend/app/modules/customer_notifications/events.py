from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class BotBlockedByUserEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    user_id: int
