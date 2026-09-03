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

_API_BASE: Final[str] = "https://gw.donut.business"
_TIMEOUT_S: Final[float] = 20.0
_OK_STATUSES: Final[frozenset[str]] = frozenset({"processing", "success", "created"})


def _sign(parts: list[tuple[str, object]], secret: str) -> str:
    chunks = [f"{key}={value}" for key, value in parts if value not in (None, "")]
    message = "".join(chunks)
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class DonutGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload: dict[str, object] = {
            "token": self._settings["token"],
            "order_id": order.idempotency_key,
            "amount": {
                "value": f"{order.final_price:.2f}",
                "currency": order.currency.value.upper(),
            },
            "customer": {"id": str(order.user_id)},
            "redirect": "true",
            "description": "CARD",
            "callback_url": self._webhook_url,
            "return_url": self._return_url,
        }
        method_id = self._settings.get("method_id")
        if method_id:
            payload["method_id"] = method_id
        payload["signature"] = self._sign_payin(payload)

        response = await _client.post(f"{_API_BASE}/p2p_payin", content=orjson.dumps(payload))
        response.raise_for_status()
        data = orjson.loads(response.content)

        status = data.get("status") or {}
        if status.get("type") not in _OK_STATUSES:
            raise PaymentGatewayError(f"Donut API error: {status.get('error_description') or data}")

        details = data.get("details") or {}
        payment_url = data.get("redirect_url") or details.get("qrcode_url") or self._return_url
        transaction_id = data.get("transaction_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(transaction_id) if transaction_id else None,
        )

    def _sign_payin(self, payload: dict[str, object]) -> str:
        amount = dict(payload["amount"])  # type: ignore[call-overload]
        customer = dict(payload["customer"])  # type: ignore[call-overload]
        parts = [
            ("token", payload["token"]),
            ("order_id", payload["order_id"]),
            ("amount.value", amount["value"]),
            ("amount.currency", amount["currency"]),
            ("customer.id", customer["id"]),
            ("redirect", payload["redirect"]),
        ]
        return _sign(parts, self._settings["secret"])

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            payload = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Donut webhook") from error

        received_sign = payload.get("signature")
        if not received_sign:
            raise PaymentGatewayError("Donut webhook missing 'signature'")

        amount = payload.get("amount") or {}
        status = payload.get("status") or {}
        parts = [
            ("token", payload.get("token")),
            ("transaction_id", payload.get("transaction_id")),
            ("order_id", payload.get("order_id")),
            ("amount.value", amount.get("value")),
            ("amount.currency", amount.get("currency")),
            ("recalculated", payload.get("recalculated")),
            ("status.type", status.get("type")),
        ]
        expected = _sign(parts, self._settings["secret"])
        if not hmac.compare_digest(expected.lower(), str(received_sign).lower()):
            raise PaymentGatewayError("Invalid Donut webhook signature")

        order_ref = payload.get("order_id")
        transaction_id = payload.get("transaction_id")
        if not order_ref or not status.get("type"):
            raise PaymentGatewayError("Donut webhook missing 'order_id'/'status.type'")

        if status.get("type") != "success":
            return None
        return WebhookResult(
            reference=str(order_ref),
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(transaction_id) if transaction_id else None,
        )
