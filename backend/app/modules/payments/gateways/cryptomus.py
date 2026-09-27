import base64
from typing import Any, ClassVar, Final, Optional

import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    link_lifetime,
    md5_hex,
    parse_json,
    safe_equals,
    signing_json,
    to_decimal,
)

_MIN_LIFETIME_S: Final[int] = 300
_MAX_LIFETIME_S: Final[int] = 43200
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"paid", "paid_over"})
_REPORTED_STATUSES: Final[dict[str, PaymentOrderStatus]] = {
    "cancel": PaymentOrderStatus.CANCELED,
    "fail": PaymentOrderStatus.FAILED,
    "system_fail": PaymentOrderStatus.FAILED,
    "wrong_amount": PaymentOrderStatus.FAILED,
    "refund_paid": PaymentOrderStatus.REFUNDED,
}


# Docs: https://doc.cryptomus.com/
class CryptomusGateway(PaymentGateway):
    currency = Currency.USD
    API_BASE: ClassVar[str] = "https://api.cryptomus.com"

    def _sign(self, body: bytes) -> str:
        return md5_hex(base64.b64encode(body).decode("ascii") + self._require("api_key"))

    def _signed(self, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = orjson.dumps(payload)
        headers = {
            "merchant": self._require("merchant_id"),
            "sign": self._sign(body),
            "Content-Type": "application/json",
        }
        return body, headers

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        body, headers = self._signed(
            {
                "amount": f"{order.final_price:.2f}",
                "currency": order.currency.value,
                "order_id": order.idempotency_key,
                "url_return": self._return_url,
                "url_success": self._return_url,
                "url_callback": self._webhook_url,
                "lifetime": link_lifetime(
                    order, unit="seconds", minimum=_MIN_LIFETIME_S, maximum=_MAX_LIFETIME_S
                ),
                "is_payment_multiple": False,
            }
        )
        response = await http_client.post(
            f"{self.API_BASE}/v1/payment", content=body, headers=headers
        )
        response.raise_for_status()
        result = orjson.loads(response.content).get("result") or {}
        payment_url = result.get("url")
        if not payment_url:
            raise PaymentGatewayError(f"{type(self).__name__} response missing 'url'")
        invoice_uuid = result.get("uuid")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(invoice_uuid) if invoice_uuid else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = parse_json(request.body, type(self).__name__)
        received_sign = data.pop("sign", None)
        expected = self._sign(signing_json(data, escape_unicode=False))
        if not received_sign or not safe_equals(expected, str(received_sign)):
            raise PaymentGatewayError(f"Invalid {type(self).__name__} webhook signature")

        order_ref = data.get("order_id")
        if not order_ref:
            raise PaymentGatewayError(f"{type(self).__name__} webhook missing 'order_id'")
        invoice_uuid = data.get("uuid")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=data.get("status") in _PAID_STATUSES,
            provider_payment_id=str(invoice_uuid) if invoice_uuid else None,
            reported_status=_REPORTED_STATUSES.get(str(data.get("status"))),
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        body, headers = self._signed({"order_id": order.idempotency_key})
        response = await http_client.post(
            f"{self.API_BASE}/v1/payment/info",
            content=body,
            headers=headers,
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        result = orjson.loads(response.content).get("result") or {}
        invoice_uuid = result.get("uuid")
        return ProviderPayment(
            paid=result.get("status") in _PAID_STATUSES,
            amount=to_decimal(result.get("amount")),
            currency=result.get("currency"),
            reference=str(result.get("order_id") or ""),
            provider_payment_id=str(invoice_uuid) if invoice_uuid else None,
        )
