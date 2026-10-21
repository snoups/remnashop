from app.core.enums import Locale, Role
from app.core.event_bus import EventBus
from app.modules.settings import AccessSettingsChangedEvent
from app.modules.transactions import subscribers
from app.modules.users import UserDto
from tests.fakes.events import stored_event

_ADMIN = UserDto(id=1, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


async def test_only_a_reenable_kicks_the_waitlist(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    kicked: list[bool] = []

    async def _kiq() -> None:
        kicked.append(True)

    monkeypatch.setattr(subscribers.notify_payment_waitlist_task, "kiq", _kiq)
    bus = EventBus()
    subscribers.register_subscribers(bus)

    for reenabled in (False, True):
        event = AccessSettingsChangedEvent(
            actor=_ADMIN, changed_fields=["payments_enabled"], payments_reenabled=reenabled
        )
        await bus.dispatch_stored(stored_event(event))

    assert kicked == [True]
