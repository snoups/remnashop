from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class BannerChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    name: str
    locale: Optional[str] = None
