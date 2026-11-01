from typing import Final

from app.modules.customer_notifications.dispatch import NotifyCustomerDispatch

# no event class of its own: the waitlist broadcast of an AccessSettingsChangedEvent
PAYMENTS_RESTORED: Final[str] = "PaymentsRestored"


class PaymentsRestoredNotices:
    """transactions' PaymentsRestoredNotifier: each waiting customer gets a regular notification."""

    def __init__(self, notify: NotifyCustomerDispatch) -> None:
        self._notify = notify

    async def notify(self, user_ids: list[int], outbox_id: int) -> None:
        for user_id in user_ids:
            await self._notify.kiq(
                user_id=user_id, event_type=PAYMENTS_RESTORED, outbox_id=outbox_id, args={}
            )
