from dataclasses import dataclass
from typing import Any, ClassVar

from app.core.events import EventCategory, SystemEvent, UserEvent


@dataclass(frozen=True, kw_only=True)
class SubscriptionPurchasedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    plan_id: int
    purchase_type: str


@dataclass(frozen=True, kw_only=True)
class SubscriptionRenewedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    duration_days: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    previous_plan_snapshot: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class SubscriptionAddOnGrantedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    addon_id: int
    amount: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionStatusSyncedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    old_status: str
    new_status: str
    source: str
