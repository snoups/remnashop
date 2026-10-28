from typing import Any, Optional, Protocol


class SendCustomerTelegramDispatch(Protocol):
    async def kiq(
        self,
        *,
        user_id: int,
        text: str,
        buttons: list[dict[str, str]],
        notification: dict[str, Any],
    ) -> object: ...


class NotifyCustomerDispatch(Protocol):
    async def kiq(
        self,
        *,
        user_id: int,
        event_type: str,
        outbox_id: int,
        args: dict[str, Any],
        payment_key: Optional[str] = None,
        subscription_id: Optional[int] = None,
        telegram_refused: bool = False,
    ) -> object: ...


class ShowPaymentCanceledDispatch(Protocol):
    async def kiq(self, *, order_id: int) -> object: ...
