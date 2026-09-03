from typing import Protocol

from app.modules.payments.dto import PaymentOrderDto


class PaymentGateway(Protocol):
    async def create_payment(
        self, order: PaymentOrderDto, settings: dict[str, str]
    ) -> tuple[str, str]:
        """Returns (external_payment_id, confirmation_url)."""
        ...

    async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
        """True only if the provider's own record confirms the payment succeeded."""
        ...
