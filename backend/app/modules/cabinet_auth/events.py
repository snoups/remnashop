from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import CabinetSignInMethod
from app.core.events import BaseEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class EmailCodeAttemptsExhaustedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    email_hash: str


@dataclass(frozen=True, kw_only=True)
class CabinetNewDeviceSignInEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    browser: str


@dataclass(frozen=True, kw_only=True)
class CabinetSignedInEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    method: CabinetSignInMethod
