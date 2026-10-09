from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import Locale
from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class LocaleActivatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class DefaultLocaleChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class LocaleDeactivatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    locale: Locale
