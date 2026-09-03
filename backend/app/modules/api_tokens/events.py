from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class ApiTokenCreatedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    token_id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class ApiTokenRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    token_id: int
