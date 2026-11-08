from datetime import timedelta
from typing import Final, Union

from sqlalchemy import ARRAY, ColumnElement, Text, func, literal, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.models.event_log import EventLogEntry

# Noisy panel and system events; everything else (money, access, admin and
# security actions) is kept for good. tests/modules/event_log/test_retention.py
# checks that every event type is placed on one side or the other.
SHORT_RETENTION: Final[timedelta] = timedelta(days=90)
SHORT_RETENTION_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        # subscriptions, as reported by the panel
        "SubscriptionDeviceAddedEvent",
        "SubscriptionDeviceRemovedEvent",
        "SubscriptionExpiredAgoEvent",
        "SubscriptionExpiredEvent",
        "SubscriptionExpiringEvent",
        "SubscriptionFirstConnectedEvent",
        "SubscriptionNotConnectedEvent",
        "SubscriptionStatusSyncedEvent",
        "SubscriptionTrafficLimitedEvent",
        "SubscriptionTrafficResetEvent",
        "SubscriptionTrafficThresholdEvent",
        "TorrentBlockerReportEvent",
        # infrastructure
        "BackupCompletedEvent",
        "BackupFailedEvent",
        "BotStartedEvent",
        "BotStoppedEvent",
        "NodeBillingDueEvent",
        "NodeConnectionLostEvent",
        "NodeConnectionRestoredEvent",
        "NodeTrafficReachedEvent",
        "PanelStartedEvent",
        "RemnawaveRestoredEvent",
        "RemnawaveUnavailableEvent",
        "RemnawaveVersionMismatchEvent",
        "RequiredChannelCheckFailedEvent",
        "TelegramWebhookFailedEvent",
    }
)

# the snapshot keys that identify a person; id and role stay for the record
_IDENTIFYING_KEYS: Final[list[str]] = ["login", "name", "username", "email", "telegram_id"]
_SNAPSHOT_KEYS: Final[tuple[str, ...]] = ("actor", "target", "user")

_LogRow = Union[type[EventLogEntry], type[EventOutboxEntry]]


async def anonymize_snapshots(
    session: AsyncSession,
    model: _LogRow,
    user_id: int,
    *scope: ColumnElement[bool],
) -> None:
    """Strip the identifying fields from every snapshot of `user_id` in the payloads."""
    for key in _SNAPSHOT_KEYS:
        snapshot = model.payload[key]
        await session.execute(
            update(model)
            # compared as text: a payload's id may be anything, a cast would fail the statement
            .where(*scope, snapshot["id"].astext == str(user_id))
            .values(
                payload=func.jsonb_set(
                    model.payload,
                    literal([key], ARRAY(Text)),
                    snapshot.op("-")(literal(_IDENTIFYING_KEYS, ARRAY(Text))),
                )
            )
            .execution_options(synchronize_session=False)
        )
