from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional

from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class PlanChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PLANS
    action: Literal[
        "access",
        "base_price",
        "create",
        "delete",
        "discount",
        "durations",
        "price_override",
        "reorder",
        "squads",
        "update",
    ]
    plan_id: Optional[int] = None
    disabled_promocode_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class AddOnChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    action: Literal["base_price", "create", "delete", "price_override", "update"]
    addon_id: Optional[int] = None
