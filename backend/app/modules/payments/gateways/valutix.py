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

_API_BASE: Final[str] = "https://api.panel.valutix.kz"
_TIMEOUT_S: Final[float] = 20.0

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class ValutixGateway(PaymentGateway):
    currency = Currency.USD

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "externalId": order.idempotency_key,
            "purpose": f"Order #{order.id}",
            "successUrl": self._return_url,
            "failUrl": self._return_url,
            "callbackUrl": self._webhook_url,
            "currency": order.currency.value,
        }
        response = await _client.post(
            f"{_API_BASE}/v1/orders",
            json=payload,
            headers={"X-Api-Token": self._settings["api_key"]},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        payment_link = data.get("paymentLink")
        if not payment_link:
            raise PaymentGatewayError("Valutix response missing 'paymentLink'")
        provider_id = data.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_link),
            provider_payment_id=str(provider_id) if provider_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-signature")
        if not signature:
            raise PaymentGatewayError("Valutix webhook missing X-Signature header")
        expected = hmac.new(
            self._settings["api_key"].encode("utf-8"), request.body, hashlib.sha512
        ).hexdigest()
        if not hmac.compare_digest(signature.lower(), expected):
            raise PaymentGatewayError("Invalid Valutix webhook signature")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Valutix webhook") from error

        provider_id = data.get("id")
        if not provider_id:
            raise PaymentGatewayError("Valutix webhook missing 'id'")

        if data.get("status") != "COMPLETED":
            return None
        return WebhookResult(
            reference="", status=PaymentOrderStatus.PAID, provider_payment_id=str(provider_id)
        )
