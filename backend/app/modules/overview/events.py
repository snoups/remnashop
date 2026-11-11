from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class RemnawaveUnavailableEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    error: str


@dataclass(frozen=True, kw_only=True)
class RemnawaveRestoredEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE


@dataclass(frozen=True, kw_only=True)
class RemnawaveVersionMismatchEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    version: str
    supported: str


@dataclass(frozen=True, kw_only=True)
class SystemHealthDegradedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    kind: str
    subject: str
    value: int


@dataclass(frozen=True, kw_only=True)
class SystemHealthRestoredEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    kind: str
    subject: str
