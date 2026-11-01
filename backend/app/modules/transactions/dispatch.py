from typing import Protocol


class ConfirmStarsPaymentDispatch(Protocol):
    async def kiq(
        self, *, telegram_id: int, payload: str, currency: str, total_amount: int, charge_id: str
    ) -> object: ...


class NotifyPaymentWaitlistDispatch(Protocol):
    async def kiq(self, *, outbox_id: int) -> object: ...


class MarkOrderFulfilledDispatch(Protocol):
    async def kiq(self, *, payment_key: str, subscription_id: int) -> object: ...
