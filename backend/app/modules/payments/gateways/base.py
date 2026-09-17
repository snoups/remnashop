from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Optional

import httpx

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto

_HTTP_TIMEOUT_S: Final[float] = 20.0
http_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S)


@dataclass(frozen=True, kw_only=True)
class WebhookRequest:
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class PaymentIntent:
    confirmation_url: Optional[str]
    provider_payment_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class WebhookSignal:
    reference: str
    claims_paid: bool
    provider_payment_id: Optional[str] = None
    # Set only where the signature binds the amount and the status API
    # reports a net figure (Robokassa, YooMoney).
    amount: Optional[Decimal] = None


@dataclass(frozen=True, kw_only=True)
class ProviderPayment:
    paid: bool
    amount: Optional[Decimal]
    reference: str
    currency: Optional[str] = None
    provider_payment_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class WebhookAck:
    body: str = ""
    media_type: str = "text/plain"


NOT_PAID: Final[ProviderPayment] = ProviderPayment(paid=False, amount=None, reference="")


def amount_to_float(value: Decimal) -> float:
    """Round to 2 places on the Decimal before the float conversion, so
    gateways needing a JSON number agree with the ones formatting a string."""
    return float(f"{value:.2f}")


class PaymentGateway(ABC):
    currency: Currency
    ack: WebhookAck = WebhookAck()

    def __init__(self, *, settings: dict[str, str], webhook_url: str, return_url: str) -> None:
        self._settings = settings
        self._webhook_url = webhook_url
        self._return_url = return_url

    def _require(self, key: str) -> str:
        value = self._settings.get(key)
        if not value:
            raise PaymentGatewayError(f"{type(self).__name__}: missing required setting '{key}'")
        return value

    def _optional(self, key: str) -> Optional[str]:
        return self._settings.get(key) or None

    @abstractmethod
    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent: ...

    @abstractmethod
    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        """Authenticate the notification where the provider signs it and
        extract references. None for notifications that are not about a
        payment. Raise PaymentGatewayError on a failed check."""

    @abstractmethod
    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        """Read the payment from the provider's status API. The decision to
        credit it is confirm()'s, not the adapter's."""

    async def confirm(
        self, order: PaymentOrderDto, signal: WebhookSignal
    ) -> Optional[ProviderPayment]:
        payment = await self.fetch_payment(order, signal)
        if not payment.paid:
            return None
        if payment.reference != order.idempotency_key:
            return None
        if payment.amount is not None and payment.amount < order.final_price:
            return None
        if payment.currency is not None and payment.currency.upper() != order.currency.value:
            return None
        return payment

    def webhook_ack(self, signal: Optional[WebhookSignal]) -> WebhookAck:
        return self.ack
