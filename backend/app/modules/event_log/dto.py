from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Optional

from app.core.dto import BaseDto
from app.core.events import EventCategory

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200

# What the dashboard bell can show, by event_type (the event class name),
# grouped so each admin picks which groups they want in their profile.
NOTIFICATION_GROUPS: Final[dict[str, frozenset[str]]] = {
    "security": frozenset(
        {
            "SessionTheftDetectedEvent",
            "LoginFailedEvent",
            "PasskeyLoginFailedEvent",
            "OAuthLoginFailedEvent",
        }
    ),
    "failures": frozenset({"BackupFailedEvent"}),
    "requests": frozenset({"PointsWithdrawalRequestedEvent"}),
    "money": frozenset(
        {
            "SubscriptionPurchasedEvent",
            "SubscriptionRenewedEvent",
            "TransactionRefundedEvent",
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
# only the critical groups until an admin chooses otherwise
DEFAULT_NOTIFICATION_GROUPS: Final[frozenset[str]] = frozenset({"security", "failures"})
NOTIFICATIONS_LIMIT: Final[int] = 20


class EventLogEntryDto(BaseDto):
    category: EventCategory
    event_type: str
    occurred_at: datetime

    actor_id: Optional[int] = None
    actor_login: Optional[str] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None

    ip_address: Optional[str] = None

    payload: dict[str, Any] = {}

    outbox_id: Optional[int] = None
    target_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class NotificationsDto:
    items: list[EventLogEntryDto]
    unread_count: int


def notification_event_types(groups: Optional[list[str]]) -> frozenset[str]:
    chosen = DEFAULT_NOTIFICATION_GROUPS if groups is None else frozenset(groups)
    return frozenset().union(*(NOTIFICATION_GROUPS[g] for g in chosen if g in NOTIFICATION_GROUPS))


@dataclass(frozen=True, kw_only=True)
class ListEventLogDto:
    category: Optional[EventCategory] = None
    actor_id: Optional[int] = None
    target_id: Optional[int] = None
    event_type: Optional[str] = None
    search: Optional[str] = None
    occurred_from: Optional[datetime] = None
    occurred_to: Optional[datetime] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
