from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, SystemEvent, UserEvent


@dataclass(frozen=True, kw_only=True)
class BroadcastChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    action: str
    broadcast_id: int


@dataclass(frozen=True, kw_only=True)
class BroadcastScheduledEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int
    scheduled_at: str


@dataclass(frozen=True, kw_only=True)
class BroadcastCanceledEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int


@dataclass(frozen=True, kw_only=True)
class BroadcastRecalledEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int


@dataclass(frozen=True, kw_only=True)
class BroadcastStartedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int
    total: int
    promocode_dropped: bool


@dataclass(frozen=True, kw_only=True)
class BroadcastCompletedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int
    sent: int
    failed: int
    blocked: int


@dataclass(frozen=True, kw_only=True)
class BroadcastFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.BROADCAST
    broadcast_id: int
    error: str
