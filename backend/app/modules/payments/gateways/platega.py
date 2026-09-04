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
    amount_to_float,
    http_client,
)

_API_BASE: Final[str] = "https://app.platega.io"
_SINGLE_METHOD_ENDPOINT: Final[str] = "transaction/process"
_MULTI_METHOD_ENDPOINT: Final[str] = "v2/transaction/process"


class PlategaGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payment_method = self._optional("payment_method")
        payload: dict[str, object] = {
            "paymentDetails": {
                "amount": amount_to_float(order.final_price),
                "currency": order.currency.value,
            },
            "description": f"Order #{order.id}",
            "return": self._return_url,
            "failedUrl": self._return_url,
        }
        endpoint = _SINGLE_METHOD_ENDPOINT
        if payment_method:
            payload["paymentMethod"] = int(payment_method)
        else:
            endpoint = _MULTI_METHOD_ENDPOINT

        response = await http_client.post(
            f"{_API_BASE}/{endpoint}",
            json=payload,
            headers={
                "X-MerchantId": self._require("merchant_id"),
                "X-Secret": self._require("api_key"),
            },
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

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        merchant_id = request.headers.get("x-merchantid")
        secret = request.headers.get("x-secret")
        if not merchant_id or not secret:
            raise PaymentGatewayError("Platega webhook missing credential headers")
        if not compare_digest(merchant_id, self._require("merchant_id")) or not compare_digest(
            secret, self._require("api_key")
        ):
            raise PaymentGatewayError("Invalid Platega webhook credentials")

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Platega webhook") from error

        transaction_id = data.get("id")
        if data.get("status") != "CONFIRMED":
            return None
        return WebhookResult(
            reference="",
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(transaction_id) if transaction_id else None,
        )
