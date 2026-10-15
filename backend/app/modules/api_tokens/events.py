from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class ApiTokenCreatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    token_id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class ApiTokenRevokedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    token_id: int
