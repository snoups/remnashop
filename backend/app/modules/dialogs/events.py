from dataclasses import dataclass, field
from typing import ClassVar, Optional

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class DialogChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    window_key: Optional[str] = None
    changed_fields: list[str] = field(default_factory=list)
