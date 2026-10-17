from typing import Final, Optional

import orjson

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://app.platega.io"
_SINGLE_METHOD_ENDPOINT: Final[str] = "transaction/process"
_MULTI_METHOD_ENDPOINT: Final[str] = "v2/transaction/process"
_PAID_STATUS: Final[str] = "CONFIRMED"
_REPORTED_STATUSES: Final[dict[str, TransactionStatus]] = {
    "CANCELED": TransactionStatus.CANCELED,
    "CHARGEBACKED": TransactionStatus.REFUNDED,
}


# Docs: https://docs.platega.io/
class PlategaGateway(PaymentGateway):
    currency = Currency.RUB

    def _headers(self) -> dict[str, str]:
        return {
            "X-MerchantId": self._require("merchant_id"),
            "X-Secret": self._require("api_key"),
        }

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payment_method = self._optional("payment_method")
        payload: dict[str, object] = {
            "paymentDetails": {
                "amount": amount_to_float(order.final_price),
                "currency": order.currency.value,
            },
            "description": f"Order #{order.id}",
            "payload": order.idempotency_key,
            "return": self._return_url,
            "failedUrl": self._return_url,
            # Required for some merchant categories; without it antifraud is off.
            "metadata": {"userId": str(order.user_id)},
        }
        endpoint = _SINGLE_METHOD_ENDPOINT
        if payment_method:
            payload["paymentMethod"] = int(payment_method)
        else:
            endpoint = _MULTI_METHOD_ENDPOINT

        response = await self._http.post(
            f"{_API_BASE}/{endpoint}", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        transaction_id = data.get("transactionId")
        if not transaction_id:
            raise PaymentGatewayError("Platega response missing 'transactionId'")
        payment_url = data.get("redirect") or data.get("url")
        if not payment_url:
            raise PaymentGatewayError("Platega response missing 'redirect'/'url'")
        return PaymentIntent(
            confirmation_url=str(payment_url), provider_payment_id=str(transaction_id)
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        merchant_id = request.headers.get("x-merchantid", "")
        secret = request.headers.get("x-secret", "")
        if not (
            safe_equals(merchant_id, self._require("merchant_id"))
            and safe_equals(secret, self._require("api_key"))
        ):
            raise PaymentGatewayError("Invalid Platega webhook credentials")

        data = parse_json(request.body, "Platega")
        transaction_id = data.get("id")
        if not transaction_id:
            raise PaymentGatewayError("Platega webhook missing 'id'")
        return WebhookSignal(
            reference="",
            claims_paid=data.get("status") == _PAID_STATUS,
            provider_payment_id=str(transaction_id),
            reported_status=_REPORTED_STATUSES.get(str(data.get("status"))),
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{_API_BASE}/transaction/{order.external_payment_id}",
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        details = data.get("paymentDetails") or {}
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(details.get("amount")),
            currency=details.get("currency"),
            reference=str(data.get("payload") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
