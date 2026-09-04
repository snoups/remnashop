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
    amount_to_float,
    http_client,
)

_API_BASE: Final[str] = "https://severpay.io/api/merchant"


class SeverPayGateway(PaymentGateway):
    currency = Currency.RUB

    def _sign(self, body: dict[str, object]) -> str:
        sorted_body = dict(sorted(body.items()))
        return hmac.new(
            self._require("token").encode("utf-8"), orjson.dumps(sorted_body), hashlib.sha256
        ).hexdigest()

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload: dict[str, object] = {
            "order_id": order.idempotency_key,
            "amount": amount_to_float(order.final_price),
            "currency": order.currency.value,
            "client_email": order.customer_email or f"user{order.user_id}@vpn.local",
            "client_id": str(order.user_id),
            "url_return": self._return_url,
            "mid": int(self._require("mid")),
            "salt": uuid.uuid4().hex,
        }
        payload["sign"] = self._sign(payload)

        response = await http_client.post(f"{_API_BASE}/payin/create", json=payload)
        response.raise_for_status()
        data = orjson.loads(response.content)
        if data.get("status") is not True:
            raise PaymentGatewayError(f"SeverPay API error: {data.get('msg') or data}")

        result = data.get("data", {})
        payment_url = result.get("url")
        if not payment_url:
            raise PaymentGatewayError("SeverPay response missing 'url'")
        payment_id = result.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            payload = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed SeverPay webhook") from error

        received_sign = payload.get("sign")
        if not received_sign:
            raise PaymentGatewayError("SeverPay webhook missing 'sign'")
        without_sign = {key: value for key, value in payload.items() if key != "sign"}
        if not hmac.compare_digest(self._sign(without_sign), str(received_sign)):
            raise PaymentGatewayError("Invalid SeverPay webhook signature")

        if payload.get("type") != "payin":
            return None

        data = payload.get("data", {})
        payment_id = data.get("id")
        if not payment_id or not data.get("status"):
            raise PaymentGatewayError("SeverPay webhook missing 'id'/'status'")

        if data.get("status") != "success":
            return None

        order_ref = data.get("order_id")
        return WebhookResult(
            reference=str(order_ref) if order_ref else "",
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(payment_id),
        )
