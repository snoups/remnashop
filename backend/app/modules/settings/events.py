from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class OidcIssuerChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
