from dataclasses import dataclass, field
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class VapidKeysGeneratedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    subscriptions_removed: int


@dataclass(frozen=True, kw_only=True)
class NotificationSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)
