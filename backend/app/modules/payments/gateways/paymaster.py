from typing import Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    format_utc,
    parse_json,
    to_decimal,
)

_API_BASE: Final[str] = "https://paymaster.ru/api/v2"
_PAID_STATUS: Final[str] = "Settled"


# Docs: https://paymaster.ru/docs/en/api
class PayMasterGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._require('api_key')}",
            "Accept": "application/json",
        }

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "merchantId": self._require("merchant_id"),
            "invoice": {
                "description": f"Order #{order.id}",
                "orderNo": order.idempotency_key,
                "expires": format_utc(order.expires_at),
            },
            "amount": {
                "value": amount_to_float(order.final_price),
                "currency": order.currency.value,
            },
            "protocol": {"returnUrl": self._return_url, "callbackUrl": self._webhook_url},
        }
        response = await http_client.post(
            f"{_API_BASE}/invoices",
            json=payload,
            headers={**self._headers(), "Idempotency-Key": order.idempotency_key},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        payment_id = data.get("paymentId")
        if not payment_id:
            raise PaymentGatewayError("PayMaster response missing 'paymentId'")
        payment_url = data.get("url")
        if not payment_url:
            raise PaymentGatewayError("PayMaster response missing 'url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=str(payment_id))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # PayMaster does not sign notifications; fetch_payment is the check.
        data = parse_json(request.body, "PayMaster")
        payment_id = data.get("id")
        if not payment_id:
            raise PaymentGatewayError("PayMaster webhook missing 'id'")
        invoice = data.get("invoice") or {}
        return WebhookSignal(
            reference=str(invoice.get("orderNo") or ""),
            claims_paid=data.get("status") == _PAID_STATUS,
            provider_payment_id=str(payment_id),
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await http_client.get(
            f"{_API_BASE}/payments/{order.external_payment_id}",
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        amount = data.get("amount") or {}
        order_no = (data.get("invoice") or {}).get("orderNo")
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(amount.get("value")),
            currency=amount.get("currency"),
            reference=str(order_no or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
