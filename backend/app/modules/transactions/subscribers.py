from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.settings import AccessSettingsChangedEvent
from app.modules.transactions.tasks import notify_payment_waitlist_task


async def _notify_waitlist(event: AccessSettingsChangedEvent, entry: StoredEvent) -> None:
    if event.payments_reenabled:
        await notify_payment_waitlist_task.kiq()  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(AccessSettingsChangedEvent, _notify_waitlist)
