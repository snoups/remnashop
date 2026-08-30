from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorTargetEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class TelegramUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class AdminCreatedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminPromotedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminPermissionsUpdatedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None


@dataclass(frozen=True, kw_only=True)
class AdminDemotedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminDeletedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class UserDeletedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
