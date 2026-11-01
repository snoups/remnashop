from typing import Protocol


class PromocodeLiveness(Protocol):
    async def is_live(self, promocode_id: int) -> bool: ...


class PaymentsRestoredNotifier(Protocol):
    # queues the "payments are back" notice for each user, as a notification of that outbox event
    async def notify(self, user_ids: list[int], outbox_id: int) -> None: ...
