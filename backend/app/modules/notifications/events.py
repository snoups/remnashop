from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class VapidKeysGeneratedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    subscriptions_removed: int
