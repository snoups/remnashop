from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from app.core.events import EventCategory, SystemEvent, UserEvent

if TYPE_CHECKING:
    from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class SubscriptionPurchasedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    plan_id: int
    purchase_type: str
    # The paid order's idempotency key; None for trial/promocode/referral grants.
    payment_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionRenewedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    duration_days: int
    payment_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    previous_subscription_id: int
    previous_plan_snapshot: dict[str, Any]
    payment_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionAddOnGrantedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    # the subscription's owner -- `user` is the system actor on the promocode path
    target: Optional[UserDto]
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


@dataclass(frozen=True, kw_only=True)
class SubscriptionEditedEvent(UserEvent):
    """An admin's manual change to a subscription, outside any purchase."""

    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    action: str
    subscription_id: int
    changed_fields: list[str] = field(default_factory=list)
