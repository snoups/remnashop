from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.event_bus import EventBus
from app.core.events import EventCategory, StoredEvent
from app.modules.notifications.dto import NOTIFICATION_GROUPS
from app.modules.notifications.subscribers import register_subscribers
from app.modules.notifications.tasks import deliver_notification_task


def test_subscribes_to_exactly_the_grouped_event_types() -> None:
    bus = EventBus()
    register_subscribers(bus)
    assert set(bus._handlers) == frozenset().union(*NOTIFICATION_GROUPS.values())


async def test_subscriber_passes_the_outbox_id(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []

    async def capture(**kwargs: Any) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(deliver_notification_task, "kiq", capture)
    bus = EventBus()
    register_subscribers(bus)
    await bus.dispatch_stored(
        StoredEvent(
            outbox_id=7,
            category=EventCategory.AUTH,
            event_type="LoginFailedEvent",
            occurred_at=datetime.now(timezone.utc),
            payload={"login": "x"},
            actor_id=None,
            actor_login=None,
            actor_name=None,
            actor_email=None,
            ip_address="1.2.3.4",
        )
    )

    assert sent and sent[0]["outbox_id"] == 7
