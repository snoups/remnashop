from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, UserEvent
from app.modules.identity_links.dto import IdentityKind


@dataclass(frozen=True, kw_only=True)
class SignInMethodLinkedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    kind: IdentityKind


@dataclass(frozen=True, kw_only=True)
class SignInMethodUnlinkedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    kind: IdentityKind
