from typing import Protocol


class SendCustomerTelegramDispatch(Protocol):
    async def kiq(self, *, user_id: int, text: str) -> object: ...
