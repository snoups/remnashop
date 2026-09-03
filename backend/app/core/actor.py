from dataclasses import dataclass
from typing import Optional, Protocol

from app.core.enums import Role


class Actor(Protocol):
    id: int
    role: Role
    name: str
    permission_grants: Optional[list[str]]
    permission_revokes: Optional[list[str]]

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
