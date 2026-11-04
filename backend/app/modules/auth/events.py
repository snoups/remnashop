from dataclasses import dataclass
from typing import ClassVar, Literal, Optional, TypeAlias

from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, SystemEvent, UserEvent

RescueCliAction: TypeAlias = Literal[
    "enable_password_login", "reset_owner_access", "restore_backup", "reset_encrypted_secrets"
]


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
class OtherSessionsRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    kept_session_id: int


@dataclass(frozen=True, kw_only=True)
class UserSessionRevokedByAdminEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


@dataclass(frozen=True, kw_only=True)
class RescueCliUsedEvent(SystemEvent):
    """A break-glass action run from `python -m app.cli` on the server."""

    category: ClassVar[EventCategory] = EventCategory.AUTH
    # reset_owner_access | enable_password_login | restore_backup | reset_encrypted_secrets
    action: RescueCliAction
    user_id: Optional[int] = None
