import base64
import hashlib
import json
from hmac import compare_digest
from typing import ClassVar, Final, Optional

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
    ip_in_networks,
)

_LIFETIME_S: Final[int] = 1800
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"paid", "paid_over"})


class CryptomusGateway(PaymentGateway):
    currency = Currency.USD
    trusted_networks = ("91.227.144.54/32",)
    API_BASE: ClassVar[str] = "https://api.cryptomus.com"

    def _sign(self, body: bytes) -> str:
        encoded = base64.b64encode(body).decode()
        return hashlib.md5(f"{encoded}{self._require('api_key')}".encode()).hexdigest()

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "currency": order.currency.value,
            "order_id": order.idempotency_key,
            "url_return": self._return_url,
            "url_success": self._return_url,
            "url_callback": self._webhook_url,
            "lifetime": _LIFETIME_S,
            "is_payment_multiple": False,
        }
        body = orjson.dumps(payload)
        response = await http_client.post(
            f"{self.API_BASE}/v1/payment",
            content=body,
            headers={
                "merchant": self._require("merchant_id"),
                "sign": self._sign(body),
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        result = orjson.loads(response.content).get("result", {})
        payment_url = result.get("url")
        if not payment_url:
            raise PaymentGatewayError("Cryptomus response missing 'url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        if not ip_in_networks(request.client_ip or "", self.trusted_networks):
            raise PaymentGatewayError("Cryptomus webhook from an untrusted IP")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Cryptomus webhook") from error

        received_sign = data.pop("sign", None)
        # Cryptomus signs its own PHP json_encode() output (escapes non-ASCII by
        # default) -- orjson doesn't escape it, so re-serializing with orjson
        # can produce different bytes and fail a legitimate signature.
        resigned = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode()
        if not received_sign or not compare_digest(self._sign(resigned), str(received_sign)):
            raise PaymentGatewayError("Invalid Cryptomus webhook signature")

        order_ref = data.get("order_id")
        if not order_ref:
            raise PaymentGatewayError("Cryptomus webhook missing 'order_id'")

        if data.get("status") not in _PAID_STATUSES:
            return None
        return WebhookResult(reference=str(order_ref), status=PaymentOrderStatus.PAID)
