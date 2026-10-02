import uuid
from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://rollypay.io/api/v1"
_PAID_STATUS: Final[str] = "paid"
_REPORTED_STATUSES: Final[dict[str, TransactionStatus]] = {
    "canceled": TransactionStatus.CANCELED,
    "expired": TransactionStatus.CANCELED,
    "refunded": TransactionStatus.REFUNDED,
    "chargeback": TransactionStatus.REFUNDED,
}


def _is_paid(data: dict[str, Any]) -> bool:
    return data.get("status") == _PAID_STATUS and data.get("test") is not True


# Docs: https://docs.rollypay.io/
class RollyPayGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._require("api_key"), "X-Nonce": uuid.uuid4().hex}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "payment_currency": order.currency.value,
            "order_id": order.idempotency_key,
            "description": f"Order #{order.id}",
            "redirect_url": self._return_url,
            "success_redirect_url": self._return_url,
            "fail_redirect_url": self._return_url,
        }
        response = await self._http.post(
            f"{_API_BASE}/payments", json=payload, headers=self._headers()
        )
        data = orjson.loads(response.content)
        if response.is_error:
            error_message = data.get("message") or data.get("error") or str(data)
            raise PaymentGatewayError(f"RollyPay API error: {error_message}")

        payment_url = data.get("pay_url")
        if not payment_url:
            raise PaymentGatewayError("RollyPay response missing 'pay_url'")
        payment_id = data.get("payment_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("x-signature", "")
        timestamp = request.headers.get("x-timestamp", "")
        if not signature or not timestamp:
            raise PaymentGatewayError("RollyPay webhook missing signature/timestamp headers")
        message = timestamp.encode("utf-8") + b"." + request.body
        if not safe_equals(hmac_hex(self._require("signing_secret"), message), signature):
            raise PaymentGatewayError("Invalid RollyPay webhook signature")

        data = parse_json(request.body, "RollyPay")
        payment_id = data.get("payment_id")
        # RollyPay retries anything but 2xx; an unusable shape is a no-op ack.
        if not payment_id or not data.get("status"):
            return None
        return WebhookSignal(
            reference=str(data.get("order_id") or ""),
            claims_paid=_is_paid(data),
            provider_payment_id=str(payment_id),
            reported_status=_REPORTED_STATUSES.get(str(data.get("status"))),
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        payment_id = order.external_payment_id or signal.provider_payment_id
        if not payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{_API_BASE}/payments/{payment_id}",
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return ProviderPayment(
            paid=_is_paid(data),
            amount=to_decimal(data.get("amount")),
            currency=data.get("payment_currency"),
            reference=str(data.get("order_id") or ""),
            provider_payment_id=str(data.get("payment_id") or payment_id),
        )
