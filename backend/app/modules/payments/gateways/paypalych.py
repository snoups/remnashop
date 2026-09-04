import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Final, Optional
from urllib.parse import parse_qs

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

_API_BASE: Final[str] = "https://pal24.pro/api/v1"
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"PAID", "SUCCESS", "OVERPAID"})


def _parse_body(body: bytes) -> dict[str, str]:
    """Pal24 posts JSON or form-encoded, depending on the shop config."""
    try:
        parsed = orjson.loads(body)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    except orjson.JSONDecodeError:
        pass
    form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] for key, values in form.items()}


class PaypalychGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": f"{order.final_price:.2f}",
            "shop_id": self._require("shop_id"),
            "currency_in": order.currency.value,
            "type": "normal",
            "order_id": order.idempotency_key,
            "description": f"Order #{order.id}",
        }
        response = await http_client.post(
            f"{_API_BASE}/bill/create",
            json=payload,
            headers={"Authorization": f"Bearer {self._require('api_token')}"},
        )
        data = orjson.loads(response.content)
        if not data.get("success", response.status_code < 400):
            raise PaymentGatewayError(
                f"Pal24 API error: {data.get('message') or data.get('error') or data}"
            )

        bill_id = data.get("bill_id")
        if not bill_id:
            raise PaymentGatewayError("Pal24 response missing 'bill_id'")

        payment_url = data.get("transfer_url") or data.get("link_page_url") or data.get("link_url")
        if not payment_url:
            raise PaymentGatewayError("Pal24 response missing a payment URL")

        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=str(bill_id))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            data = _parse_body(request.body)
        except UnicodeDecodeError as error:
            raise PaymentGatewayError("Malformed Pal24 webhook") from error

        out_sum = data.get("OutSum")
        inv_id = data.get("InvId")
        signature = data.get("SignatureValue")
        status = data.get("Status")
        if not out_sum or not inv_id or not signature or not status:
            raise PaymentGatewayError(
                "Pal24 webhook missing 'InvId'/'OutSum'/'Status'/'SignatureValue'"
            )

        expected = (
            hashlib.md5(f"{out_sum}:{inv_id}:{self._require('signature_token')}".encode("utf-8"))
            .hexdigest()
            .upper()
        )
        if not hmac.compare_digest(expected, signature.upper()):
            raise PaymentGatewayError("Invalid Pal24 webhook signature")

        if status.upper() not in _PAID_STATUSES:
            return None

        try:
            amount = Decimal(str(out_sum))
        except InvalidOperation:
            amount = None

        provider_payment_id = data.get("TrsId")
        return WebhookResult(
            reference=inv_id,
            status=PaymentOrderStatus.PAID,
            provider_payment_id=provider_payment_id,
            amount=amount,
        )

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return '{"status": "ok"}'
