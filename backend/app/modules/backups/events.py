from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class BackupFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    run_id: int
    kind: str
    error: str
