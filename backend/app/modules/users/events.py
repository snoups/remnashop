from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class TelegramUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    # Pass-through only -- users never resolves or stores this, advertising
    # does via an EventBus subscriber (see modules/advertising/events.py).
    ad_link_code: Optional[str] = None


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


@dataclass(frozen=True, kw_only=True)
class UserBlockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UserUnblockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class TelegramRegistrationBlockedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UsersBulkBlockedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    count: int


@dataclass(frozen=True, kw_only=True)
class UsersBulkUnblockedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    count: int
