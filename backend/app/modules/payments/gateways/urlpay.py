import hashlib
from decimal import Decimal, InvalidOperation
from hmac import compare_digest
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

_API_BASE: Final[str] = "https://urlpay.io/api"
_PAYMENT_SUBJECT: Final[int] = 4
_PAYMENT_MODE: Final[int] = 4


class UrlPayGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        currency = order.currency.value
        amount = f"{order.final_price:.2f}"
        shop_id = int(self._require("shop_id"))
        vat_code = self._optional("vat_code")
        payload: dict[str, object] = {
            "currency": currency,
            "amount": amount,
            "uuid": order.idempotency_key,
            "shopId": shop_id,
            "description": f"Order #{order.id}",
            "sign": self._sign(currency, amount, shop_id),
            "items": [
                {
                    "description": f"Order #{order.id}",
                    "quantity": 1,
                    "price": float(amount),
                    "vat_code": int(vat_code) if vat_code else None,
                    "payment_subject": _PAYMENT_SUBJECT,
                    "payment_mode": _PAYMENT_MODE,
                }
            ],
        }
        response = await http_client.post(
            f"{_API_BASE}/v2/payments",
            json=payload,
            headers={"Authorization": f"Bearer {self._require('api_key')}"},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("success"):
            raise PaymentGatewayError(f"UrlPay API error: {data}")

        payment_url = data.get("paymentUrl")
        if not payment_url:
            raise PaymentGatewayError("UrlPay response missing 'paymentUrl'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed UrlPay webhook") from error

        order_ref = data.get("uuid")
        if not order_ref:
            raise PaymentGatewayError("UrlPay webhook missing 'uuid'")

        if not self._signature_valid(data):
            raise PaymentGatewayError("Invalid UrlPay webhook signature")

        if data.get("payment_status") != "success":
            return None

        try:
            amount = Decimal(str(data.get("amount", "")))
        except InvalidOperation:
            amount = None

        return WebhookResult(reference=order_ref, status=PaymentOrderStatus.PAID, amount=amount)

    def _signature_valid(self, data: dict[str, object]) -> bool:
        received_sign = data.get("sign")
        if not received_sign:
            return False
        currency = str(data.get("currency", "rub")).lower()
        try:
            amount = f"{Decimal(str(data.get('amount', ''))):.2f}"
        except Exception:  # noqa: BLE001 -- any unparseable amount fails verification
            return False
        expected = self._sign(currency, amount, int(self._require("shop_id")))
        return compare_digest(expected, str(received_sign))

    def _sign(self, currency: str, amount: str, shop_id: int) -> str:
        raw = f"{currency}{amount}{shop_id}{self._require('secret_key')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
