import hashlib
import hmac
from typing import Final, Optional

import httpx
import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
)

_API_BASE: Final[str] = "https://app.aurapay.tech"
_TIMEOUT_S: Final[float] = 20.0

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class AuraPayGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-ApiKey": self._settings["api_key"],
            "X-ShopId": self._settings["shop_id"],
        }

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": float(order.final_price),
            "order_id": order.idempotency_key,
            "comment": f"Order #{order.id}",
            "success_url": self._return_url,
            "fail_url": self._return_url,
            "callback_url": self._webhook_url,
        }
        response = await _client.post(
            f"{_API_BASE}/invoice/create", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        payment_data = data.get("payment_data") or {}
        payment_url = payment_data.get("url") if isinstance(payment_data, dict) else None
        if not payment_url:
            raise PaymentGatewayError("AuraPay response missing 'payment_data.url'")
        invoice_id = data.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-signature")
        if not signature:
            raise PaymentGatewayError("AuraPay webhook missing X-SIGNATURE header")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed AuraPay webhook") from error

        if not self._signature_valid(data, signature):
            raise PaymentGatewayError("Invalid AuraPay webhook signature")

        invoice_id = data.get("id")
        order_ref = data.get("order_id")
        if not invoice_id or not order_ref:
            raise PaymentGatewayError("AuraPay webhook missing 'id'/'order_id'")

        if data.get("status") != "PAID":
            return None
        return WebhookResult(
            reference=str(order_ref),
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(invoice_id),
        )

    def _signature_valid(self, data: dict[str, object], signature: str) -> bool:
        # Sort keys alphabetically, concatenate stringified values (None -> ""),
        # HMAC-SHA256 with the shop's secret key.
        concatenated = "".join(
            str(data[key]) if data[key] is not None else "" for key in sorted(data)
        )
        expected = hmac.new(
            self._settings["secret_key"].encode("utf-8"),
            concatenated.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
