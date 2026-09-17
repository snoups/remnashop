from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    link_lifetime,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://app.aurapay.tech"
_PAID_STATUS: Final[str] = "PAID"
_MAX_LIFETIME_MINUTES: Final[int] = 43200


class AuraPayGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-ApiKey": self._require("api_key"),
            "X-ShopId": self._require("shop_id"),
        }

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": amount_to_float(order.final_price),
            "order_id": order.idempotency_key,
            "comment": f"Order #{order.id}",
            "success_url": self._return_url,
            "fail_url": self._return_url,
            "callback_url": self._webhook_url,
            "lifetime": link_lifetime(order, unit="minutes", maximum=_MAX_LIFETIME_MINUTES),
        }
        response = await http_client.post(
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

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("x-signature", "")
        data = parse_json(request.body, "AuraPay")
        if not signature or not safe_equals(self._signature(data), signature, ignore_case=True):
            raise PaymentGatewayError("Invalid AuraPay webhook signature")

        invoice_id = data.get("id")
        order_ref = data.get("order_id")
        if not invoice_id or not order_ref:
            raise PaymentGatewayError("AuraPay webhook missing 'id'/'order_id'")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=data.get("status") == _PAID_STATUS,
            provider_payment_id=str(invoice_id),
        )

    def _signature(self, data: dict[str, Any]) -> str:
        concatenated = "".join(
            "" if value is None else str(value) for _, value in sorted(data.items())
        )
        return hmac_hex(self._require("secret_key"), concatenated.encode("utf-8"))

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await http_client.post(
            f"{_API_BASE}/invoice/status",
            json={"id": order.external_payment_id},
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(data.get("amount")),
            currency=Currency.RUB.value,
            reference=str(data.get("order_id") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
