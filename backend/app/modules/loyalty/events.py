from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorTargetEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class LoyaltySettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS


@dataclass(frozen=True, kw_only=True)
class UserLoyaltyExclusionChangedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    excluded: bool
