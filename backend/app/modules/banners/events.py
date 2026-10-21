from dataclasses import dataclass
from typing import ClassVar, Literal, Optional

from app.core.enums import Locale
from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class BannerChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["delete", "reset_default", "upload"]
    name: str
    locale: Optional[Locale] = None
