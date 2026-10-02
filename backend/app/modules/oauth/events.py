from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import OAuthProvider
from app.core.events import BaseEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class OAuthLoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthLoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityConnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityDisconnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider
