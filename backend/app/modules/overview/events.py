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
