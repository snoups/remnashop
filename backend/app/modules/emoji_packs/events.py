from dataclasses import dataclass
from typing import ClassVar, Literal

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class EmojiPackChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["delete", "import"]
    set_name: str
