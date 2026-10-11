from dataclasses import dataclass, field
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class OidcIssuerChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS


@dataclass(frozen=True, kw_only=True)
class EmailSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CabinetAuthSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class AccessSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)
    payments_reenabled: bool = False


@dataclass(frozen=True, kw_only=True)
class ShopSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BotRequirementsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)
