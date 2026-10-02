from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class PlanChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PLANS
    action: str
    plan_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class AddOnChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    action: str
    addon_id: Optional[int] = None
