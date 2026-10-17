from typing import Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    format_utc,
    parse_json,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.paypear.ru/v1"
_DEFAULT_PAYMENT_METHOD: Final[str] = "sbp"
_PAID_STATUS: Final[str] = "CONFIRMED"
_PAID_EVENT: Final[str] = "payment.confirmed"


# Docs: https://paypear.ru/docs/
class PayPearGateway(PaymentGateway):
    currency = Currency.RUB

    def _auth(self) -> tuple[str, str]:
        return self._require("shop_id"), self._require("secret_key")

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
            "order_id": order.idempotency_key,
            "payment_method_data": {"type": _DEFAULT_PAYMENT_METHOD},
            "description": f"Order #{order.id}",
            "confirmation": {"type": "redirect", "return_url": self._return_url},
            "webhook_url": self._webhook_url,
            "expires_at": format_utc(order.expires_at),
        }
        # The docs spell the header both ways; send both.
        response = await self._http.post(
            f"{_API_BASE}/payment/",
            json=payload,
            auth=self._auth(),
            headers={
                "Idempotence-Key": order.idempotency_key,
                "Idempotency-Key": order.idempotency_key,
            },
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if data.get("success") is not True:
            raise PaymentGatewayError(f"PayPear API error: {data.get('message') or data}")

        result = data.get("result") or {}
        confirmation = result.get("confirmation") or {}
        payment_url = confirmation.get("confirmation_url") or confirmation.get("url")
        if not payment_url:
            raise PaymentGatewayError("PayPear response missing a confirmation URL")
        payment_id = result.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # the `signature` field has no published algorithm, so fetch_payment
        # is what authenticates the payment
        data = parse_json(request.body, "PayPear")
        obj = data.get("object") or {}
        payment_id = obj.get("id")
        if not payment_id:
            raise PaymentGatewayError("PayPear webhook missing 'object.id'")
        return WebhookSignal(
            reference=str(obj.get("order_id") or ""),
            claims_paid=data.get("event") == _PAID_EVENT,
            provider_payment_id=str(payment_id),
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{_API_BASE}/payment/{order.external_payment_id}/",
            auth=self._auth(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        result = orjson.loads(response.content).get("result") or {}
        amount = result.get("amount") or {}
        return ProviderPayment(
            paid=result.get("status") == _PAID_STATUS,
            amount=to_decimal(amount.get("value")),
            currency=amount.get("currency"),
            reference=str(result.get("order_id") or ""),
            provider_payment_id=str(result.get("id") or order.external_payment_id),
        )
