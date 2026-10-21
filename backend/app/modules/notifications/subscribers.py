from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.notifications.dto import NOTIFICATION_GROUPS
from app.modules.notifications.tasks import deliver_notification_task


async def _deliver(entry: StoredEvent) -> None:
    # fields, not the event-log row: this runs inside the outbox transaction,
    # so the row may not be committed when the task starts
    await deliver_notification_task.kiq(  # type: ignore[call-overload]
        outbox_id=entry.outbox_id,
        event_type=entry.event_type,
        payload=entry.payload,
        actor_id=entry.actor_id,
        ip_address=entry.ip_address,
    )


def register_subscribers(bus: EventBus) -> None:
    for event_types in NOTIFICATION_GROUPS.values():
        for event_type in event_types:
            bus.subscribe_stored(event_type, _deliver)
