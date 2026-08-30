from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class PromocodeActivatedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PROMOCODE
    promocode_id: int
    reward_type: str
