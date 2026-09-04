from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import auto
from typing import TYPE_CHECKING, Any, ClassVar, Optional
from uuid import UUID, uuid4

from app.core.enums import UpperStrEnum
from app.core.utils.time import datetime_now

if TYPE_CHECKING:
    # modules.users itself imports app.core.events at module scope (directly, and
    # transitively via app.core.ports) -- an eager import here would cycle back
    # into a partially-initialized modules.users.
    from app.modules.users import UserDto


class EventCategory(UpperStrEnum):
    AUTH = auto()
    ADMIN_MANAGEMENT = auto()
    USER = auto()
    SETTINGS = auto()
    SUBSCRIPTION = auto()
    PROMOCODE = auto()
    REFERRAL = auto()
    PRICING = auto()
    PLANS = auto()


@dataclass(frozen=True, kw_only=True)
class BaseEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime_now)
    ip_address: Optional[str] = None
    category: ClassVar[EventCategory]

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True, kw_only=True)
class SystemEvent(BaseEvent): ...


@dataclass(frozen=True, kw_only=True)
class UserEvent(BaseEvent):
    user: UserDto


@dataclass(frozen=True, kw_only=True)
class ActorEvent(BaseEvent):
    actor: UserDto


@dataclass(frozen=True, kw_only=True)
class ActorTargetEvent(ActorEvent):
    target: UserDto


@dataclass(frozen=True, kw_only=True)
class StoredEvent:
    outbox_id: int
    category: EventCategory
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]
    actor_id: Optional[int]
    actor_login: Optional[str]
    actor_name: Optional[str]
    actor_email: Optional[str]
    ip_address: Optional[str]
