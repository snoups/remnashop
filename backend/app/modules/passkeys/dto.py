from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Optional

from app.core.dto import BaseDto, TimestampMixin

RP_NAME: Final[str] = "Remnashop"


class PasskeyCredentialDto(BaseDto, TimestampMixin):
    user_id: int
    credential_id: str
    public_key: bytes
    sign_count: int
    transports: Optional[list[str]] = None
    device_type: str
    backed_up: bool
    name: Optional[str] = None
    last_used_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class CreatePasskeyCredentialDto:
    user_id: int
    credential_id: str
    public_key: bytes
    sign_count: int
    transports: Optional[list[str]]
    device_type: str
    backed_up: bool
    name: Optional[str]


@dataclass(frozen=True, kw_only=True)
class RenamePasskeyDto:
    id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class VerifyPasskeyRegistrationDto:
    credential: dict[str, Any]
    name: Optional[str]
