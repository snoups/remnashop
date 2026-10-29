from dataclasses import dataclass
from typing import ClassVar, Literal

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class ConnectGuideChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["reset", "update"]
