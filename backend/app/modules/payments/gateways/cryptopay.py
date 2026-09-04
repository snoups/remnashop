import hashlib
import hmac
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

_API_BASE: Final[str] = "https://pay.crypt.bot/api"
_EXPIRES_IN_S: Final[int] = 1800


class CryptoPayGateway(PaymentGateway):
    currency = Currency.USD

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "currency_type": "fiat",
            "fiat": order.currency.value,
            "amount": f"{order.final_price:.2f}",
            "description": f"Order #{order.id}",
            "payload": order.idempotency_key,
            "paid_btn_name": "openBot",
            "paid_btn_url": self._return_url,
            "expires_in": _EXPIRES_IN_S,
        }
        response = await http_client.post(
            f"{_API_BASE}/createInvoice",
            json=payload,
            headers={"Crypto-Pay-API-Token": self._require("api_key")},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("ok"):
            raise PaymentGatewayError(f"CryptoPay API error: {data.get('error')}")

        payment_url = data.get("result", {}).get("bot_invoice_url")
        if not payment_url:
            raise PaymentGatewayError("CryptoPay response missing 'bot_invoice_url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("crypto-pay-api-signature")
        if not signature:
            raise PaymentGatewayError("CryptoPay webhook missing signature header")
        secret = hashlib.sha256(self._require("api_key").encode()).digest()
        expected = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentGatewayError("Invalid CryptoPay webhook signature")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed CryptoPay webhook") from error

        if data.get("update_type") != "invoice_paid":
            return None

        invoice = data.get("payload", {})
        order_ref = invoice.get("payload")
        if not order_ref:
            raise PaymentGatewayError("CryptoPay invoice missing 'payload'")

        if invoice.get("status") != "paid":
            return None
        return WebhookResult(reference=str(order_ref), status=PaymentOrderStatus.PAID)
