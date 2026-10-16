from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorEvent, EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class BackupFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    run_id: int
    kind: str
    error: str


@dataclass(frozen=True, kw_only=True)
class BackupChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    run_id: Optional[int] = None
    kind: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class BackupCompletedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    run_id: int
    kind: str
    size_bytes: int
