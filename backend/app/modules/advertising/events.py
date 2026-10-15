from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class AdLinkChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    ad_link_id: int
