import base64
import hashlib
import hmac
from typing import Final, Optional
from urllib.parse import parse_qs, unquote_plus

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

_API_BASE: Final[str] = "https://api.cloudpayments.ru"
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"Completed", "Authorized"})


class CloudPaymentsGateway(PaymentGateway):
    currency = Currency.RUB

    def _basic_auth(self) -> str:
        credentials = f"{self._require('public_id')}:{self._require('api_secret')}"
        return "Basic " + base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "Amount": amount_to_float(order.final_price),
            "Currency": order.currency.value,
            "Description": f"Order #{order.id}",
            "AccountId": str(order.user_id),
            "InvoiceId": order.idempotency_key,
            "SuccessRedirectUrl": self._return_url,
            "FailRedirectUrl": self._return_url,
        }
        response = await http_client.post(
            f"{_API_BASE}/orders/create",
            json=payload,
            headers={"Authorization": self._basic_auth(), "Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("Success"):
            raise PaymentGatewayError(f"CloudPayments API error: {data.get('Message') or data}")

        model = data.get("Model") or {}
        payment_url = model.get("Url")
        if not payment_url:
            raise PaymentGatewayError("CloudPayments response missing 'Model.Url'")
        order_id = model.get("Id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(order_id) if order_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("content-hmac") or request.headers.get("x-content-hmac")
        if not signature:
            raise PaymentGatewayError("CloudPayments webhook missing Content-HMAC header")
        secret = self._require("api_secret")
        if not self._signature_matches(secret, request.body, signature):
            raise PaymentGatewayError("Invalid CloudPayments webhook signature")

        fields = {key: values[0] for key, values in parse_qs(request.body.decode("utf-8")).items()}

        order_ref = fields.get("InvoiceId")
        transaction_id = fields.get("TransactionId")
        status = fields.get("Status", "")
        if not order_ref or not status:
            raise PaymentGatewayError("CloudPayments webhook missing 'InvoiceId'/'Status'")

        # Pay notifications carry Reason or AuthCode; the pre-charge Check
        # notification carries neither and must not be treated as payment.
        is_pay_notification = bool(fields.get("Reason") or fields.get("AuthCode"))
        if status not in _PAID_STATUSES or not is_pay_notification:
            return None

        return WebhookResult(
            reference=order_ref,
            status=PaymentOrderStatus.PAID,
            provider_payment_id=transaction_id,
        )

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return '{"code": 0}'

    @staticmethod
    def _signature_matches(secret: str, raw_body: bytes, signature: str) -> bool:
        def calc(data: bytes) -> str:
            return base64.b64encode(
                hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
            ).decode()

        if hmac.compare_digest(calc(raw_body), signature):
            return True
        try:
            decoded = unquote_plus(raw_body.decode("utf-8")).encode("utf-8")
        except UnicodeDecodeError:
            return False
        return hmac.compare_digest(calc(decoded), signature)
