from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol

from app.core.enums import Role


class Actor(Protocol):
    id: int
    role: Role
    name: str
    permission_grants: Optional[list[str]]
    permission_revokes: Optional[list[str]]
    # Contact/balance fields a UserDto carries and a SyntheticActor (API token)
    # structurally lacks -- declared here as the common shape so consumers read
    # them as typed attributes instead of getattr(actor, ..., default).
    telegram_id: Optional[int]
    email: Optional[str]
    login: Optional[str]
    ip_allowlist: Optional[list[str]]
    referral_code: Optional[str]
    points: Decimal

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
    telegram_id: Optional[int] = None
    email: Optional[str] = None
    login: Optional[str] = None
    ip_allowlist: Optional[list[str]] = None
    referral_code: Optional[str] = None
    points: Decimal = Decimal(0)
