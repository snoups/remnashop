from dataclasses import dataclass
from typing import Final, Optional, Protocol, runtime_checkable

from app.core.enums import Role


@runtime_checkable
class Actor(Protocol):
    id: int
    role: Role
    name: str
    permission_grants: Optional[list[str]]
    permission_revokes: Optional[list[str]]
    # identity only, for the audit trail; None for an API token
    login: Optional[str]
    email: Optional[str]
    telegram_id: Optional[int]

    @property
    def is_privileged(self) -> bool: ...

    @property
    def log(self) -> str: ...


@dataclass
class SyntheticActor:
    id: int
    role: Role
    name: str
    is_privileged: bool
    log: str
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None
    login: Optional[str] = None
    email: Optional[str] = None
    telegram_id: Optional[int] = None


SYSTEM_ACTOR: Final[SyntheticActor] = SyntheticActor(
    id=-1, role=Role.SYSTEM, name=Role.SYSTEM.name, is_privileged=True, log="[SYSTEM]"
)


def actor_user_id(actor: Actor) -> Optional[int]:
    # an API token (0) and SYSTEM (-1) have no users row to reference
    return actor.id if actor.id > 0 else None
