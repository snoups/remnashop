import hashlib
import hmac
import uuid
from typing import Final, Optional

import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
    http_client,
)

_API_BASE: Final[str] = "https://rollypay.io/api/v1"


class RollyPayGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "payment_currency": order.currency.value,
            "order_id": order.idempotency_key,
            "description": f"Order #{order.id}",
            "redirect_url": self._return_url,
            "success_redirect_url": self._return_url,
            "fail_redirect_url": self._return_url,
        }
        response = await http_client.post(
            f"{_API_BASE}/payments",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self._require("api_key"),
                "X-Nonce": uuid.uuid4().hex,
            },
        )
        data = orjson.loads(response.content)
        if response.status_code != 200:
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

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-signature")
        timestamp = request.headers.get("x-timestamp")
        if not signature or not timestamp:
            raise PaymentGatewayError("RollyPay webhook missing signature/timestamp headers")

        message = f"{timestamp}.{request.body.decode('utf-8')}"
        expected = hmac.new(
            self._require("signing_secret").encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentGatewayError("Invalid RollyPay webhook signature")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed RollyPay webhook") from error

        payment_id = data.get("payment_id")
        status_value = data.get("status")
        # RollyPay retries with exponential backoff on anything but a 200 --
        # a shape this adapter can't act on is a no-op ack, not a rejection.
        if not payment_id or not status_value:
            return None

        is_paid = data.get("event_type") == "payment.paid" or status_value == "paid"
        if not is_paid:
            return None

        order_ref = data.get("order_id")
        return WebhookResult(
            reference=str(order_ref) if order_ref else "",
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(payment_id),
        )
