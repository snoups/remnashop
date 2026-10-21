from typing import ClassVar, Final, Optional, Protocol

import orjson
from pydantic import SecretStr

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.gateways import GatewaySettings, RioPaySettings
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    parse_json,
    safe_equals,
    to_decimal,
)

_PAID_STATUS: Final[str] = "COMPLETED"
_REPORTED_STATUSES: Final[dict[str, TransactionStatus]] = {
    "CANCELED": TransactionStatus.CANCELED,
    "FAILED": TransactionStatus.FAILED,
    "EXPIRED": TransactionStatus.CANCELED,
}


class _RioPayFamilySettings(Protocol):
    # RioPay calls its token api_token, Valutix api_key
    @property
    def token(self) -> SecretStr: ...

    @property
    def service_id(self) -> Optional[str]: ...


# Docs: https://docs.riopay.online/ru/docs
class RioPayGateway(PaymentGateway[_RioPayFamilySettings]):
    settings_model: ClassVar[type[GatewaySettings]] = RioPaySettings
    currency = Currency.RUB
    API_BASE: ClassVar[str] = "https://api.riopay.online"

    def _token(self) -> str:
        return self.settings.token.get_secret_value()

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload: dict[str, object] = {
            "amount": f"{order.final_price:.2f}",
            "currency": order.currency.value,
            "externalId": order.idempotency_key,
            "purpose": f"Order #{order.id}",
            "successUrl": self._return_url,
            "failUrl": self._return_url,
            "callbackUrl": self._webhook_url,
        }
        service_id = self.settings.service_id
        if service_id:
            payload["serviceId"] = int(service_id)

        response = await self._http.post(
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

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
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
