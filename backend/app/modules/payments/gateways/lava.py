import hashlib
import hmac
from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
    amount_to_float,
    http_client,
)

_API_BASE: Final[str] = "https://api.lava.ru"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    """sort_keys JSON, 'signature' excluded -- legacy fallback canonicalization
    some Lava shops sign instead of the raw request/webhook body."""

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key != "signature"}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    without_sig = normalize(payload)
    return orjson.dumps(without_sig, option=orjson.OPT_SORT_KEYS)


class LavaGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "sum": amount_to_float(order.final_price),
            "orderId": order.idempotency_key,
            "shopId": self._require("shop_id"),
            "hookUrl": self._webhook_url,
            "successUrl": self._return_url,
            "failUrl": self._return_url,
        }
        body = orjson.dumps(payload)
        signature = hmac.new(
            self._require("secret_key").encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        response = await http_client.post(
            f"{_API_BASE}/business/invoice/create",
            content=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Signature": signature,
            },
        )
        response.raise_for_status()
        result = orjson.loads(response.content)
        if str(result.get("status", "")).lower() == "error":
            raise PaymentGatewayError(f"Lava API error: {result.get('error') or result}")

        data = result.get("data") or result
        payment_url = data.get("url") or data.get("payment_url")
        if not payment_url:
            raise PaymentGatewayError("Lava response missing 'url'")
        invoice_id = data.get("id") or data.get("invoice_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("authorization")
        if not signature:
            raise PaymentGatewayError("Lava webhook missing Authorization header")
        secret = self._require("webhook_secret").encode("utf-8")

        if not self._signature_matches(secret, request.body, signature):
            raise PaymentGatewayError("Invalid Lava webhook signature")

        try:
            payload = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Lava webhook") from error

        order_ref = payload.get("order_id")
        status = str(payload.get("status") or "").strip().lower()
        if not order_ref or not status:
            raise PaymentGatewayError("Lava webhook missing 'order_id'/'status'")

        if status != "success":
            return None
        invoice_id = payload.get("invoice_id")
        return WebhookResult(
            reference=str(order_ref),
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    def _signature_matches(self, secret: bytes, raw_body: bytes, received: str) -> bool:
        received = received.strip()
        expected_raw = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_raw.lower(), received.lower()):
            return True
        try:
            payload = orjson.loads(raw_body)
        except orjson.JSONDecodeError:
            return False
        if not isinstance(payload, dict):
            return False
        expected_canonical = hmac.new(secret, _canonical_json(payload), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_canonical.lower(), received.lower())
