from collections.abc import Iterable
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import auto
from typing import Annotated, Any, ClassVar, Final, Optional, TypeVar, get_type_hints

from pydantic import BeforeValidator, PlainSerializer, TypeAdapter

from app.core.actor import Actor
from app.core.enums import Role, UpperStrEnum
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
    BROADCAST = auto()
    INFRASTRUCTURE = auto()


@dataclass(frozen=True, kw_only=True)
class BaseEvent:
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


def _role_from_name(value: object) -> object:
    return Role[value] if isinstance(value, str) else value


# stored by name ("ADMIN"), as the audit log has always shown it
_StoredRole = Annotated[
    Role, BeforeValidator(_role_from_name), PlainSerializer(str, return_type=str)
]


@dataclass(frozen=True, kw_only=True)
class ActorSnapshot:
    """The identity an event stores for an Actor; what a subscriber gets back."""

    id: int
    login: Optional[str]
    name: str
    role: _StoredRole
    telegram_id: Optional[int]
    username: Optional[str]
    email: Optional[str]
    # not stored: an event records who acted, not what they were allowed
    permission_grants: ClassVar[Optional[list[str]]] = None
    permission_revokes: ClassVar[Optional[list[str]]] = None

    @classmethod
    def of(cls, actor: Actor) -> "ActorSnapshot":
        return cls(
            id=actor.id,
            login=actor.login,
            name=actor.name,
            role=actor.role,
            telegram_id=actor.telegram_id,
            username=actor.username,
            email=actor.email,
        )

    @property
    def is_privileged(self) -> bool:
        return self.role.includes(Role.ADMIN)

    @property
    def is_system(self) -> bool:
        return self.role == Role.SYSTEM

    @property
    def log(self) -> str:
        return f"[{self.role}:{self.id}:{self.login or self.name}]"

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = _SNAPSHOT_ADAPTER.dump_python(self, mode="json")
        return payload


_SNAPSHOT_ADAPTER: Final[TypeAdapter[ActorSnapshot]] = TypeAdapter(ActorSnapshot)


E = TypeVar("E", bound=BaseEvent)
# stored in the outbox row's columns, not in the payload
EVENT_ROW_FIELDS: Final[frozenset[str]] = frozenset({"occurred_at", "ip_address"})


def _stored_type(hint: Any) -> Any:
    # an Actor is stored as its snapshot, and comes back as one
    if hint is Actor:
        return ActorSnapshot
    if hint == Optional[Actor]:
        return Optional[ActorSnapshot]
    return hint


_ADAPTERS: Final[dict[type[BaseEvent], tuple[tuple[str, TypeAdapter[Any]], ...]]] = {}


def _payload_adapters(event_type: type[BaseEvent]) -> tuple[tuple[str, TypeAdapter[Any]], ...]:
    if event_type not in _ADAPTERS:
        hints = get_type_hints(event_type)
        _ADAPTERS[event_type] = tuple(
            (f.name, TypeAdapter(_stored_type(hints[f.name])))
            for f in fields(event_type)
            if f.name not in EVENT_ROW_FIELDS
        )
    return _ADAPTERS[event_type]


def restore_event(event_type: type[E], entry: StoredEvent) -> E:
    """Rebuilds the event an outbox row was written from; a field missing from an
    older row takes its default."""
    values: dict[str, Any] = {
        name: adapter.validate_python(entry.payload[name])
        for name, adapter in _payload_adapters(event_type)
        if name in entry.payload
    }
    return event_type(occurred_at=entry.occurred_at, ip_address=entry.ip_address, **values)


def changed_fields(before: object, after: object, names: Iterable[str]) -> list[str]:
    """Names whose value differs between two snapshots of the same record."""
    return sorted(name for name in names if getattr(before, name) != getattr(after, name))


MASKED_IP: Final[str] = "***"
# no actor recorded, yet the address is a staff member's sign-in attempt
_STAFF_SIGN_IN_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "LoginFailedEvent",
        "BootstrapConflictEvent",
        "OAuthLoginFailedEvent",
        "PasskeyLoginFailedEvent",
        "SessionTheftDetectedEvent",
        "PanelLoginSucceededEvent",
        "PanelLoginFailedEvent",
    }
)


def visible_ip(
    reader: Actor, owner_id: Optional[int], owner_role: Role, ip_address: Optional[str]
) -> Optional[str]:
    """A staff member's address is shown only to them and to roles above theirs."""
    if ip_address is None or reader.id == owner_id:
        return ip_address
    if owner_role.includes(Role.ADMIN) and not reader.role > owner_role:
        return MASKED_IP
    return ip_address


def visible_event_ip(
    reader: Actor,
    event_type: str,
    payload: dict[str, Any],
    ip_address: Optional[str],
    current_role: Optional[Role] = None,
) -> Optional[str]:
    """The address is the acting person's; ``current_role`` covers a customer promoted since."""
    snapshot = payload.get("actor") or payload.get("user")
    if isinstance(snapshot, dict):
        owner_id = snapshot.get("id")
        owner_role = Role.__members__.get(str(snapshot.get("role")), Role.USER)
        # an API token is issued by the owner
        if owner_id == 0:
            owner_role = Role.OWNER
    elif event_type in _STAFF_SIGN_IN_EVENT_TYPES:
        owner_id, owner_role = None, Role.ADMIN
    else:
        return ip_address
    if current_role is not None:
        owner_role = max(owner_role, current_role)
    return visible_ip(reader, owner_id, owner_role, ip_address)
