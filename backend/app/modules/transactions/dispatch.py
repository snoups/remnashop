from typing import Protocol


class ConfirmStarsPaymentDispatch(Protocol):
    async def kiq(
        self, *, telegram_id: int, payload: str, currency: str, total_amount: int, charge_id: str
    ) -> object: ...
