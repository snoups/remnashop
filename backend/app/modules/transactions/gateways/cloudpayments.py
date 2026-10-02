from typing import Final, Optional

import orjson

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_b64,
    parse_form,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.cloudpayments.ru"
# Single-stage payments only; Authorized is a two-stage hold.
_PAID_STATUS: Final[str] = "Completed"
_DECLINED_STATUS: Final[str] = "Declined"


# Docs: https://developers.cloudpayments.ru/
class CloudPaymentsGateway(PaymentGateway):
    currency = Currency.RUB
    ack = WebhookAck(body='{"code": 0}', media_type="application/json")

    def _auth(self) -> tuple[str, str]:
        return self._require("public_id"), self._require("api_secret")

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "Amount": amount_to_float(order.final_price),
            "Currency": order.currency.value,
            "Description": f"Order #{order.id}",
            "AccountId": str(order.user_id),
            "InvoiceId": order.idempotency_key,
            "SuccessRedirectUrl": self._return_url,
            "FailRedirectUrl": self._return_url,
        }
        response = await self._http.post(
            f"{_API_BASE}/orders/create", json=payload, auth=self._auth()
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

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("content-hmac")
        expected = hmac_b64(self._require("api_secret"), request.body)
        if not signature or not safe_equals(expected, signature):
            raise PaymentGatewayError("Invalid CloudPayments webhook signature")

        fields = parse_form(request.body, "CloudPayments")
        order_ref = fields.get("InvoiceId")
        if not order_ref:
            raise PaymentGatewayError("CloudPayments webhook missing 'InvoiceId'")
        return WebhookSignal(
            reference=order_ref,
            claims_paid=fields.get("Status") == _PAID_STATUS,
            provider_payment_id=fields.get("TransactionId") or None,
            reported_status=TransactionStatus.FAILED
            if fields.get("Status") == _DECLINED_STATUS
            else None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        response = await self._http.post(
            f"{_API_BASE}/payments/find",
            json={"InvoiceId": order.idempotency_key},
            auth=self._auth(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("Success"):
            return NOT_PAID
        model = data.get("Model") or {}
        transaction_id = model.get("TransactionId")
        return ProviderPayment(
            paid=model.get("Status") == _PAID_STATUS,
            amount=to_decimal(model.get("Amount")),
            currency=model.get("Currency"),
            reference=str(model.get("InvoiceId") or ""),
            provider_payment_id=str(transaction_id) if transaction_id else None,
        )
