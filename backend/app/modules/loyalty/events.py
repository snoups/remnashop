from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, ActorTargetEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class LoyaltySettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SETTINGS


@dataclass(frozen=True, kw_only=True)
class UserLoyaltyExclusionChangedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    excluded: bool
