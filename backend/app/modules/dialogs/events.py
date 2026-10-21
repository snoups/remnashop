from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class DialogChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["buttons", "create", "delete", "import", "reset", "reset_all", "text", "update"]
    window_key: Optional[str] = None
    changed_fields: list[str] = field(default_factory=list)
