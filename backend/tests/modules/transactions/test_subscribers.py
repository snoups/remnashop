from app.core.events import EventCategory, StoredEvent
from app.core.utils.time import datetime_now
from app.modules.transactions import subscribers


def _entry(reenabled: bool) -> StoredEvent:
    return StoredEvent(
        outbox_id=1,
        category=EventCategory.SETTINGS,
        event_type="AccessSettingsChangedEvent",
        occurred_at=datetime_now(),
        payload={"payments_reenabled": reenabled, "changed_fields": ["payments_enabled"]},
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=None,
    )


async def test_only_a_reenable_kicks_the_waitlist(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    kicked: list[bool] = []

    async def _kiq() -> None:
        kicked.append(True)

    monkeypatch.setattr(subscribers.notify_payment_waitlist_task, "kiq", _kiq)

    await subscribers._notify_waitlist(_entry(False))
    assert kicked == []
    await subscribers._notify_waitlist(_entry(True))
    assert kicked == [True]
