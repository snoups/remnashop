from dataclasses import dataclass, field
from datetime import datetime
from enum import auto
from typing import Any, ClassVar, Optional
from uuid import UUID, uuid4

from app.core.actor import Actor
from app.core.enums import UpperStrEnum
from app.core.utils.time import datetime_now


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
    PAYMENT = auto()


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
    user: Actor


@dataclass(frozen=True, kw_only=True)
class ActorEvent(BaseEvent):
    actor: Actor


@dataclass(frozen=True, kw_only=True)
class ActorTargetEvent(ActorEvent):
    target: Actor


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


def set_fields(dto: object, *, skip: frozenset[str] = frozenset()) -> list[str]:
    """Names of a partial-update DTO's fields that carry a value -- what an
    audit event records about a change, never the values themselves."""
    return sorted(
        name for name, value in vars(dto).items() if value is not None and name not in skip
    )
