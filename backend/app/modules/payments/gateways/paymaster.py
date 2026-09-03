from typing import Final, Optional

import httpx
import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
)

_API_BASE: Final[str] = "https://paymaster.ru/api/v2"
_TIMEOUT_S: Final[float] = 15.0
_PAID_STATUSES: Final[frozenset[str]] = frozenset({"Settled", "Authorized"})

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class PayMasterGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "merchantId": self._settings["merchant_id"],
            "invoice": {"description": f"Order #{order.id}"},
            "amount": {"value": float(order.final_price), "currency": order.currency.value},
            "protocol": {"returnUrl": self._return_url, "callbackUrl": self._webhook_url},
        }
        response = await _client.post(
            f"{_API_BASE}/invoices",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._settings['api_key']}",
                "Accept": "application/json",
                "Idempotency-Key": order.idempotency_key,
            },
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        payment_id = data.get("paymentId")
        if not payment_id:
            raise PaymentGatewayError("PayMaster response missing 'paymentId'")
        payment_url = data.get("url")
        if not payment_url:
            raise PaymentGatewayError("PayMaster response missing 'url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=str(payment_id))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        # PayMaster's real API offers no documented webhook signature
        # or IP allowlist (none was ported from main either) -- any POST naming
        # a known payment id and a paid status is trusted as-is. Upgrade path:
        # pull-verify against a GET /invoices/{id} status endpoint once PayMaster's
        # real API docs are in hand, same pattern as YooKassa's verify_payment.
        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed PayMaster webhook") from error

        payment_id = data.get("id")
        if not payment_id:
            raise PaymentGatewayError("PayMaster webhook missing 'id'")

        if data.get("status") not in _PAID_STATUSES:
            return None
        return WebhookResult(
            reference="", status=PaymentOrderStatus.PAID, provider_payment_id=str(payment_id)
        )
