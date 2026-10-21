from dataclasses import dataclass
from typing import ClassVar, Literal

from app.core.enums import AdLinkChannel
from app.core.events import ActorEvent, EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class AdLinkChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS
    action: Literal["create", "delete", "update"]
    ad_link_id: int


@dataclass(frozen=True, kw_only=True)
class AdLinkAttributedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    user_id: int
    ad_link_id: int
    ad_link_code: str
    channel: AdLinkChannel
