from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional, TypeAlias

from app.core.enums import AppearanceTarget
from app.core.events import ActorEvent, EventCategory, SystemEvent

AppearanceAction: TypeAlias = Literal[
    "favicon_delete", "favicon_upload", "logo_delete", "logo_upload", "reset", "update"
]


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
    action: Literal["commands", "proxy_remove", "proxy_set", "restart", "update"]
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class AppearanceSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: AppearanceAction
    target: AppearanceTarget
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BotStartedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    username: str


@dataclass(frozen=True, kw_only=True)
class BotStoppedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    uptime_seconds: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class TelegramWebhookFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    error: str


@dataclass(frozen=True, kw_only=True)
class RequiredChannelCheckFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    channel_id: int
    error: str
