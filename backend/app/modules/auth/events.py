from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class OwnerBootstrappedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class LoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class LoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    login: str


@dataclass(frozen=True, kw_only=True)
class BootstrapConflictEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    login: str


@dataclass(frozen=True, kw_only=True)
class SessionTheftDetectedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    user_id: int
    session_id: int


@dataclass(frozen=True, kw_only=True)
class SessionRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


@dataclass(frozen=True, kw_only=True)
class UserSessionRevokedByAdminEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


@dataclass(frozen=True, kw_only=True)
class LoggedOutEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    user_id: int
    session_id: int
    audience: str
