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

_API_BASE: Final[str] = "https://api.riopay.online"
_TIMEOUT_S: Final[float] = 20.0

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class RioPayGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": str(order.final_price),
            "externalId": order.idempotency_key,
            "purpose": f"Order #{order.id}",
            "successUrl": self._return_url,
        }
        response = await _client.post(
            f"{_API_BASE}/v1/orders",
            json=payload,
            headers={
                "X-Api-Token": self._settings["api_token"],
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 201:
            data = orjson.loads(response.content) if response.content else {}
            raise PaymentGatewayError(
                f"RioPay API error: {data.get('message') or data.get('error') or response.text}"
            )

        data = orjson.loads(response.content)
        payment_url = data.get("paymentLink")
        if not payment_url:
            raise PaymentGatewayError("RioPay response missing 'paymentLink'")
        order_id = data.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(order_id) if order_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-signature")
        if not signature:
            raise PaymentGatewayError("RioPay webhook missing X-Signature header")

        # RioPay's own docs default the webhook secret to the API token when
        # a dedicated one isn't configured.
        secret = self._settings.get("webhook_secret") or self._settings["api_token"]
        expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentGatewayError("Invalid RioPay webhook signature")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed RioPay webhook") from error

        order_id = data.get("id")
        order_ref = data.get("externalId")
        if not order_id or not data.get("status"):
            raise PaymentGatewayError("RioPay webhook missing 'id'/'status'")

        if data.get("status") != "COMPLETED":
            return None
        return WebhookResult(
            reference=str(order_ref) if order_ref else "",
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(order_id),
        )
