from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import Locale
from app.core.events import BaseEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class LocaleActivatedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class LocaleDeactivatedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class OidcIssuerChangedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
