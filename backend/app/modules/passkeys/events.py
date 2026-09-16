from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import BaseEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class PasskeyLoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    credential_name: Optional[str]


@dataclass(frozen=True, kw_only=True)
class PasskeyLoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    # Absent whenever the credential itself wasn't recognised, which is most
    # of the ways this fails.
    credential_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class PasskeyRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    credential_name: Optional[str]


@dataclass(frozen=True, kw_only=True)
class PasskeyRemovedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    credential_name: Optional[str]
