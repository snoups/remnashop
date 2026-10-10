from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Optional

from pydantic import SecretStr

from app.core.dto import BaseDto

if TYPE_CHECKING:
    from app.modules.users import UserDto


class NotificationChannel(StrEnum):
    BELL = "bell"
    PUSH = "push"
    TELEGRAM = "telegram"


COALESCED_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {"LoginFailedEvent", "PasskeyLoginFailedEvent", "OAuthLoginFailedEvent"}
)
COALESCE_WINDOW_S: Final[int] = 300

NOTIFICATION_GROUPS: Final[dict[str, frozenset[str]]] = {
    "security": frozenset(
        {
            "SessionTheftDetectedEvent",
            "LoginFailedEvent",
            "PasskeyLoginFailedEvent",
            "OAuthLoginFailedEvent",
        }
    ),
    "failures": frozenset({"BackupFailedEvent", "BonusDaysRenewalStuckEvent"}),
    "broadcasts": frozenset({"BroadcastCompletedEvent", "BroadcastFailedEvent"}),
    "requests": frozenset({"PointsWithdrawalRequestedEvent"}),
    "money": frozenset(
        {
            "SubscriptionPurchasedEvent",
            "SubscriptionRenewedEvent",
            "TransactionRefundedEvent",
            "TransactionPartiallyRefundedEvent",
            "TransactionFulfilledManuallyEvent",
        }
    ),
    "admins": frozenset(
        {
            "AdminCreatedEvent",
            "AdminDeletedEvent",
            "AdminPromotedEvent",
            "AdminDemotedEvent",
            "AdminPermissionsUpdatedEvent",
        }
    ),
}

_ALL_CHANNELS: Final[frozenset[NotificationChannel]] = frozenset(NotificationChannel)
_CHANNEL_VALUES: Final[frozenset[str]] = frozenset(c.value for c in NotificationChannel)
# the bell holds the entry; a recipient may lack the event-log permissions
PUSH_URL: Final[str] = "/dashboard?bell=open"
_CRITICAL_GROUPS: Final[frozenset[str]] = frozenset({"security", "failures"})
# critical groups everywhere, the rest only in the bell, until an admin chooses otherwise
DEFAULT_NOTIFICATION_CHANNELS: Final[dict[str, frozenset[NotificationChannel]]] = {
    group: _ALL_CHANNELS if group in _CRITICAL_GROUPS else frozenset({NotificationChannel.BELL})
    for group in NOTIFICATION_GROUPS
}
_GROUP_BY_EVENT_TYPE: Final[dict[str, str]] = {
    event_type: group for group, types in NOTIFICATION_GROUPS.items() for event_type in types
}


def group_of(event_type: str) -> Optional[str]:
    return _GROUP_BY_EVENT_TYPE.get(event_type)


def channels_for(user: "UserDto", group: str) -> frozenset[NotificationChannel]:
    stored = (user.notification_channels or {}).get(group)
    # also a group added after the admin last saved the matrix
    if stored is None:
        return DEFAULT_NOTIFICATION_CHANNELS.get(group, frozenset())
    return frozenset(NotificationChannel(c) for c in stored if c in _CHANNEL_VALUES)


def bell_event_types(user: "UserDto") -> frozenset[str]:
    return frozenset().union(
        *(
            types
            for group, types in NOTIFICATION_GROUPS.items()
            if NotificationChannel.BELL in channels_for(user, group)
        )
    )


def effective_matrix(user: "UserDto") -> dict[str, list[str]]:
    return {
        group: sorted(channel.value for channel in channels_for(user, group))
        for group in NOTIFICATION_GROUPS
    }


@dataclass(frozen=True, kw_only=True)
class NotificationChannelsDto:
    channels: dict[str, list[str]]
    push_configured: bool
    telegram_available: bool


class NotificationSettingsDto(BaseDto):
    vapid_public_key: Optional[str] = None
    vapid_private_key: Optional[SecretStr] = None
    vapid_contact: Optional[str] = None

    @property
    def is_push_configured(self) -> bool:
        return self.vapid_public_key is not None and self.vapid_private_key is not None


@dataclass(frozen=True, kw_only=True)
class UpdateNotificationSettingsDto:
    vapid_contact: Optional[str] = None


class PushSubscriptionDto(BaseDto):
    user_id: int
    session_id: Optional[int] = None
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = None
    failure_count: int = 0
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class PushMessage:
    title: str
    body: str
    url: str
    tag: str


@dataclass(frozen=True, kw_only=True)
class SubscribePushDto:
    endpoint: str
    p256dh: str
    auth: str
    session_id: int
    user_agent: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class DeliverNotificationDto:
    event_type: str
    payload: dict[str, Any]
    actor_id: Optional[int]
    ip_address: Optional[str]
    suppressed: int = 0
    # the shared overflow window: the payload shown is only the last source's
    sources_merged: bool = False


@dataclass(frozen=True, kw_only=True)
class SendTelegramTextsDto:
    user_ids: list[int]
    # "<message>.<attribute>" from the bot's translations
    key: str
