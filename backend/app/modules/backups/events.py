from dataclasses import dataclass
from typing import ClassVar, Literal, Optional

from app.core.enums import BackupKind
from app.core.events import ActorEvent, EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class BackupFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    run_id: int
    kind: BackupKind
    error: str


@dataclass(frozen=True, kw_only=True)
class BackupChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["cancel", "delete", "run", "settings", "settings_reset"]
    run_id: Optional[int] = None
    kind: Optional[BackupKind] = None


@dataclass(frozen=True, kw_only=True)
class BackupCompletedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    run_id: int
    kind: BackupKind
    size_bytes: int
