from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional

from app.core.enums import PromocodeRewardType
from app.core.events import ActorEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class PromocodeActivatedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PROMOCODE
    promocode_id: int
    reward_type: PromocodeRewardType


@dataclass(frozen=True, kw_only=True)
class PromocodeChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PROMOCODE
    action: Literal["create", "delete", "update"]
    promocode_id: int
    # kept so a deleted promocode's entries still say which code it was
    code: Optional[str] = None
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class PromocodeDiscountExpiringEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PROMOCODE
    promocode_id: int
    code: str
    percent: int
    hours: int
