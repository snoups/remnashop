from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class TelegramUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    # passed through: advertising and referrals resolve these in their subscribers
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class CabinetUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    method: str
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class AdminCreatedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminPromotedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminPermissionsUpdatedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    permission_grants: Optional[list[str]] = None
    permission_revokes: Optional[list[str]] = None


@dataclass(frozen=True, kw_only=True)
class AdminDemotedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class AdminDeletedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT


@dataclass(frozen=True, kw_only=True)
class UserDeletedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class TelegramIdBoundEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    previous_telegram_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class UserBlockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UserUnblockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class TelegramRegistrationBlockedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class CabinetRegistrationBlockedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UsersBulkUnblockedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    count: int


@dataclass(frozen=True, kw_only=True)
class UserPersonalDiscountChangedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    old_percent: int
    new_percent: int


@dataclass(frozen=True, kw_only=True)
class UserPurchaseDiscountChangedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    old_percent: int
    new_percent: int


@dataclass(frozen=True, kw_only=True)
class UserRulesAcceptedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
