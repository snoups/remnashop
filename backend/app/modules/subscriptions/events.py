from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, SystemEvent, UserEvent
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class SubscriptionPurchasedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    plan_id: int
    purchase_type: str
    # The paid order's idempotency key; None for trial/promocode/referral grants.
    payment_key: Optional[str] = None
    is_trial: bool = False


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
    # the subscription's owner; `user` is the system actor on the promocode path
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
    user_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionExpiringEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    hours: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionExpiredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionTrafficLimitedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionTrafficThresholdEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionExpiredAgoEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    hours: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionNotConnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    hours: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionFirstConnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionTrafficResetEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionDeviceAddedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    hwid: str
    platform: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionDeviceRemovedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    hwid: str
    platform: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class TorrentBlockerReportEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    node_name: str
    destination: str
    blocked_until: str


@dataclass(frozen=True, kw_only=True)
class NodeConnectionLostEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    node_name: str
    message: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class NodeConnectionRestoredEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    node_name: str


@dataclass(frozen=True, kw_only=True)
class NodeTrafficReachedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    node_name: str


@dataclass(frozen=True, kw_only=True)
class NodeBillingDueEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE
    provider: str
    node_name: str
    next_billing_at: str


@dataclass(frozen=True, kw_only=True)
class PanelStartedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.INFRASTRUCTURE


@dataclass(frozen=True, kw_only=True)
class PanelLoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    username: str
    user_agent: str


@dataclass(frozen=True, kw_only=True)
class PanelLoginSucceededEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    username: str
    user_agent: str


@dataclass(frozen=True, kw_only=True)
class SubscriptionEditedEvent(ActorTargetEvent):
    """An admin's manual change to a subscription, outside any purchase."""

    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    action: str
    subscription_id: int
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class SubscriptionGrantedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    plan_id: int
    duration_days: int


@dataclass(frozen=True, kw_only=True)
class SubscriptionPlanChangedByAdminEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.SUBSCRIPTION
    subscription_id: int
    previous_subscription_id: int
    previous_plan_snapshot: dict[str, Any]
    plan_id: int
    duration_days: Optional[int] = None
