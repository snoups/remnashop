from dataclasses import dataclass
from typing import ClassVar, Literal, Optional

from app.core.enums import LegalDocumentKind, Locale, PurchaseChannel
from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class LegalDocumentChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["update", "text_set", "text_remove"]
    kind: LegalDocumentKind
    locale: Optional[Locale] = None
    channel: Optional[PurchaseChannel] = None
    changed: list[str]
