from typing import Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    http_client,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    link_lifetime,
    md5_hex,
    parse_form,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://pal24.pro/api/v1"
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"SUCCESS", "OVERPAID"})


def _parse_postback(body: bytes) -> dict[str, str]:
    """Pal24 posts JSON or form-encoded, depending on the shop config."""
    try:
        data = parse_json(body, "Pal24")
    except PaymentGatewayError:
        return parse_form(body, "Pal24")
    return {str(key): str(value) for key, value in data.items()}


# Docs: https://pally.info/reference/api
class PaypalychGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._require('api_token')}"}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "shop_id": self._require("shop_id"),
            "currency_in": order.currency.value,
            "type": "normal",
            "order_id": order.idempotency_key,
            "description": f"Order #{order.id}",
            "ttl": link_lifetime(order, unit="seconds"),
        }
        response = await http_client.post(
            f"{_API_BASE}/bill/create", json=payload, headers=self._headers()
        )
        data = orjson.loads(response.content)
        if response.is_error or str(data.get("success")).lower() != "true":
            raise PaymentGatewayError(
                f"Pal24 API error: {data.get('message') or data.get('error') or data}"
            )

        bill_id = data.get("bill_id")
        if not bill_id:
            raise PaymentGatewayError("Pal24 response missing 'bill_id'")
        payment_url = data.get("link_page_url") or data.get("link_url")
        if not payment_url:
            raise PaymentGatewayError("Pal24 response missing a payment URL")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=str(bill_id))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = _parse_postback(request.body)
        out_sum = data.get("OutSum")
        inv_id = data.get("InvId")
        signature = data.get("SignatureValue")
        status = data.get("Status")
        if not out_sum or not inv_id or not signature or not status:
            raise PaymentGatewayError(
                "Pal24 webhook missing 'InvId'/'OutSum'/'Status'/'SignatureValue'"
            )

        expected = md5_hex(f"{out_sum}:{inv_id}:{self._require('api_token')}")
        if not safe_equals(expected, signature, ignore_case=True):
            raise PaymentGatewayError("Invalid Pal24 webhook signature")

        return WebhookSignal(
            reference=inv_id,
            claims_paid=status.upper() in _PAID_STATUSES,
            provider_payment_id=data.get("TrsId") or None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await http_client.get(
            f"{_API_BASE}/bill/status",
            params={"id": order.external_payment_id},
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return ProviderPayment(
            paid=str(data.get("status")).upper() in _PAID_STATUSES,
            amount=to_decimal(data.get("amount")),
            currency=data.get("currency_in"),
            reference=str(data.get("order_id") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
