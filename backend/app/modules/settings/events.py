from dataclasses import dataclass, field
from typing import ClassVar

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class OidcIssuerChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS


@dataclass(frozen=True, kw_only=True)
class EmailSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class CabinetAuthSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class AccessSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)
    payments_reenabled: bool = False


@dataclass(frozen=True, kw_only=True)
class ShopSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BotRequirementsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BotSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class AppearanceSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: str
    changed_fields: list[str] = field(default_factory=list)
