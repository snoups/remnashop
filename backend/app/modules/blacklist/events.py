from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, BaseEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class BlacklistEntryAddedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    kind: str
    value: str


@dataclass(frozen=True, kw_only=True)
class BlacklistEntryRemovedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    kind: str
    value: str


@dataclass(frozen=True, kw_only=True)
class BlacklistReconciledEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    blocked_user_ids: list[int]
