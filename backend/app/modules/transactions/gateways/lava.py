from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    link_lifetime,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.lava.ru"
_PAID_STATUS: Final[str] = "success"
_MAX_EXPIRE_MINUTES: Final[int] = 7200


# Docs: https://developer.lava.ru/
class LavaGateway(PaymentGateway):
    currency = Currency.RUB

    def _signed(self, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        # Lava verifies the signature against the raw body byte for byte.
        body = orjson.dumps(payload)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Signature": hmac_hex(self._require("secret_key"), body),
        }
        return body, headers

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        body, headers = self._signed(
            {
                "sum": amount_to_float(order.final_price),
                "orderId": order.idempotency_key,
                "shopId": self._require("shop_id"),
                "hookUrl": self._webhook_url,
                "successUrl": self._return_url,
                "failUrl": self._return_url,
                "expire": link_lifetime(order, unit="minutes", maximum=_MAX_EXPIRE_MINUTES),
            }
        )
        response = await self._http.post(
            f"{_API_BASE}/business/invoice/create", content=body, headers=headers
        )
        response.raise_for_status()
        data = orjson.loads(response.content).get("data") or {}
        payment_url = data.get("url")
        if not payment_url:
            raise PaymentGatewayError("Lava response missing 'data.url'")
        invoice_id = data.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("signature", "").strip()
        expected = hmac_hex(self._require("webhook_secret"), request.body)
        if not signature or not safe_equals(expected, signature, ignore_case=True):
            raise PaymentGatewayError("Invalid Lava webhook signature")

        data = parse_json(request.body, "Lava")
        order_ref = data.get("order_id")
        status = str(data.get("status") or "").strip().lower()
        if not order_ref or not status:
            raise PaymentGatewayError("Lava webhook missing 'order_id'/'status'")
        invoice_id = data.get("invoice_id")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=status == _PAID_STATUS,
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        body, headers = self._signed(
            {"shopId": self._require("shop_id"), "orderId": order.idempotency_key}
        )
        response = await self._http.post(
            f"{_API_BASE}/business/invoice/status",
            content=body,
            headers=headers,
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content).get("data") or {}
        invoice_id = data.get("id")
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(data.get("amount")),
            currency=Currency.RUB.value,
            reference=str(data.get("order_id") or ""),
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )
