from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional

from app.core.enums import CabinetSignInMethod
from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, SystemEvent, UserEvent


@dataclass(frozen=True, kw_only=True)
class TelegramUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    # passed through: advertising and referrals resolve these in their subscribers
    ad_link_code: Optional[str] = None
    referral_code: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class CabinetUserRegisteredEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    method: CabinetSignInMethod
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
class TelegramIdUnboundEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    previous_telegram_id: int


@dataclass(frozen=True, kw_only=True)
class UserBlockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UserUnblockedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UserEmailUndeliverableClearedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER


@dataclass(frozen=True, kw_only=True)
class UserTrialAvailabilityChangedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    is_trial_available: bool


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
class PasswordChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class SecuritySettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BotBlockedByUserEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    user_id: int


@dataclass(frozen=True, kw_only=True)
class MarketingOptOutChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.USER
    opted_out: bool
    source: Literal["account", "link"]
