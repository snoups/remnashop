from dataclasses import dataclass, field
from typing import ClassVar

from app.core.events import ActorTargetEvent, EventCategory, UserEvent


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
class ReferralSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.REFERRAL
    action: str
    changed_fields: list[str] = field(default_factory=list)
