from typing import ClassVar, Final, Optional

import orjson

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    parse_json,
    safe_equals,
    to_decimal,
)

_PAID_STATUS: Final[str] = "COMPLETED"
_REPORTED_STATUSES: Final[dict[str, PaymentOrderStatus]] = {
    "CANCELED": PaymentOrderStatus.CANCELED,
    "FAILED": PaymentOrderStatus.FAILED,
    "EXPIRED": PaymentOrderStatus.CANCELED,
}


# Docs: https://docs.riopay.online/ru/docs
class RioPayGateway(PaymentGateway):
    currency = Currency.RUB
    API_BASE: ClassVar[str] = "https://api.riopay.online"
    TOKEN_SETTING: ClassVar[str] = "api_token"

    def _token(self) -> str:
        return self._require(self.TOKEN_SETTING)

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload: dict[str, object] = {
            "amount": f"{order.final_price:.2f}",
            "currency": order.currency.value,
            "externalId": order.idempotency_key,
            "purpose": f"Order #{order.id}",
            "successUrl": self._return_url,
            "failUrl": self._return_url,
            "callbackUrl": self._webhook_url,
        }
        service_id = self._optional("service_id")
        if service_id:
            payload["serviceId"] = int(service_id)

        response = await http_client.post(
            f"{self.API_BASE}/v1/orders", json=payload, headers={"X-Api-Token": self._token()}
        )
        if response.is_error:
            raise PaymentGatewayError(
                f"{type(self).__name__} API error {response.status_code}: {response.text[:500]}"
            )
        data = orjson.loads(response.content)
        payment_url = data.get("paymentLink")
        if not payment_url:
            raise PaymentGatewayError(f"{type(self).__name__} response missing 'paymentLink'")
        order_id = data.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(order_id) if order_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("x-signature", "")
        expected = hmac_hex(self._token(), request.body, "sha512")
        if not signature or not safe_equals(expected, signature, ignore_case=True):
            raise PaymentGatewayError(f"Invalid {type(self).__name__} webhook signature")

        data = parse_json(request.body, type(self).__name__)
        order_id = data.get("id")
        status = data.get("status")
        if not order_id or not status:
            raise PaymentGatewayError(f"{type(self).__name__} webhook missing 'id'/'status'")
        return WebhookSignal(
            reference=str(data.get("externalId") or ""),
            claims_paid=status == _PAID_STATUS,
            provider_payment_id=str(order_id),
            reported_status=_REPORTED_STATUSES.get(str(status)),
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await http_client.get(
            f"{self.API_BASE}/v1/orders/{order.external_payment_id}",
            headers={"X-Api-Token": self._token()},
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(data.get("amount")),
            currency=data.get("currency"),
            reference=str(data.get("externalId") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
