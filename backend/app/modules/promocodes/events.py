from dataclasses import dataclass
from typing import ClassVar, Literal

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


@dataclass(frozen=True, kw_only=True)
class PromocodeDiscountExpiringEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PROMOCODE
    promocode_id: int
    code: str
    percent: int
    hours: int
