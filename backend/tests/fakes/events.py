from app.core import json
from app.core.events import BaseEvent, StoredEvent
from app.core.outbox_event_publisher import _build_payload


class RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def publish(self, event: BaseEvent) -> None:
        self.events.append(event)


def stored_event(event: BaseEvent, *, outbox_id: int = 5) -> StoredEvent:
    """The outbox row for `event`, its payload through the same JSON round trip as JSONB."""
    return StoredEvent(
        outbox_id=outbox_id,
        category=event.category,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        payload=json.decode(json.encode(_build_payload(event))),
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=event.ip_address,
    )
