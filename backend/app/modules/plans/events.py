from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class PlanChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PLANS
    action: str
    plan_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class AddOnChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    action: str
    addon_id: Optional[int] = None
