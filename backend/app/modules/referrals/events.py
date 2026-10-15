from dataclasses import dataclass, field
from typing import ClassVar

from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, SystemEvent, UserEvent


@dataclass(frozen=True, kw_only=True)
class ReferralAttachedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    referrer_id: int


@dataclass(frozen=True, kw_only=True)
class ReferralRewardIssuedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    level: int
    reward_type: str
    amount: str


@dataclass(frozen=True, kw_only=True)
class PointsWithdrawalRequestedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    amount: str


@dataclass(frozen=True, kw_only=True)
class UserPointsAdjustedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    delta: str


@dataclass(frozen=True, kw_only=True)
class ReferralCodeResetEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL


@dataclass(frozen=True, kw_only=True)
class ReferralSettingsChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    action: str
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BonusDaysRedeemedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    subscription_id: int
    days: int


@dataclass(frozen=True, kw_only=True)
class UserBonusDaysAdjustedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    delta: int


@dataclass(frozen=True, kw_only=True)
class InviteeRewardIssuedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    reward_type: str
    amount: int


@dataclass(frozen=True, kw_only=True)
class ReferralRewardReversedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    amount: str
    reward_type: str
    payment_key: str


@dataclass(frozen=True, kw_only=True)
class BonusDaysRenewalStuckEvent(SystemEvent):
    # the days are debited and the date may already be on the panel; an admin finishes it
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    user_id: int
    subscription_id: int
    days: int
    idempotency_key: str
    error: str
