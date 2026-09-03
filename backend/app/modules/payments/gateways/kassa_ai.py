import hashlib
import hmac
import time
from typing import Final, Optional
from urllib.parse import parse_qs

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

_API_BASE: Final[str] = "https://api.fk.life/v1"
_TIMEOUT_S: Final[float] = 15.0
_SBP_PAYMENT_SYSTEM_ID: Final[int] = 44

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class KassaAIGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        data: dict[str, object] = {
            "shopId": int(self._settings["shop_id"]),
            "nonce": time.time_ns(),
            "paymentId": order.idempotency_key,
            "i": _SBP_PAYMENT_SYSTEM_ID,
            "email": order.customer_email or f"user_{order.idempotency_key}@telegram.org",
            # one implementation resolves the server's public IP via an
            # external IP-detection service for this antifraud field; it's
            # not part of the webhook signature, so a placeholder is enough.
            "ip": "127.0.0.1",
            "amount": f"{order.final_price:.2f}",
            "currency": order.currency.value,
            "success_url": self._return_url,
            "fail_url": self._return_url,
            "notification_url": self._webhook_url,
        }
        sorted_values = "|".join(str(value) for _, value in sorted(data.items()))
        data["signature"] = hmac.new(
            self._settings["api_key"].encode("utf-8"), sorted_values.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        response = await _client.post(f"{_API_BASE}/orders/create", json=data)
        response.raise_for_status()
        result = orjson.loads(response.content)
        if result.get("type") != "success":
            raise PaymentGatewayError(f"KassaAI API error: {result.get('error') or result}")

        payment_url = result.get("location")
        if not payment_url:
            raise PaymentGatewayError("KassaAI response missing 'location'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            parsed = parse_qs(request.body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError as error:
            raise PaymentGatewayError("Malformed KassaAI webhook") from error
        data = {key: values[0] for key, values in parsed.items()}

        merchant_id = data.get("MERCHANT_ID", "")
        if merchant_id != self._settings["shop_id"]:
            raise PaymentGatewayError("KassaAI webhook MERCHANT_ID does not match shop_id")

        order_ref = data.get("MERCHANT_ORDER_ID")
        if not order_ref:
            raise PaymentGatewayError("KassaAI webhook missing 'MERCHANT_ORDER_ID'")

        raw = f"{merchant_id}:{data.get('AMOUNT')}:{self._settings['secret_word_2']}:{order_ref}"
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(expected, data.get("SIGN", "").lower()):
            raise PaymentGatewayError("Invalid KassaAI webhook signature")

        return WebhookResult(
            reference=order_ref,
            status=PaymentOrderStatus.PAID,
            provider_payment_id=data.get("intid"),
        )

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return "YES"
