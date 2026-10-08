from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.events import EventCategory, StoredEvent
from app.modules.loyalty.subscribers import _recalculate_merged
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task


async def test_merge_recalculates_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def _kiq(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(recalculate_loyalty_discounts_task, "kiq", _kiq)
    entry = StoredEvent(
        outbox_id=1,
        category=next(iter(EventCategory)),
        event_type="AccountsMergedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"target": {"id": 7}, "source": {"id": 8}},
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=None,
    )

    await _recalculate_merged(entry)

    assert calls == [{"user_ids": [7]}]
