from typing import Final, Optional

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
from app.modules.payments.gateways.common import PROVIDER_API_TIMEOUT_S, parse_json, to_decimal

_API_BASE: Final[str] = "https://api.yookassa.ru/v3"
_PAID_STATUS: Final[str] = "succeeded"
_PAID_EVENT: Final[str] = "payment.succeeded"
_REPORTED_EVENTS: Final[dict[str, PaymentOrderStatus]] = {
    "payment.canceled": PaymentOrderStatus.CANCELED,
    "refund.succeeded": PaymentOrderStatus.REFUNDED,
}
_REFUND_EVENT_PREFIX: Final[str] = "refund."


def _build_receipt(order: PaymentOrderDto, settings: dict[str, str]) -> Optional[dict[str, object]]:
    if not order.customer_email or not settings.get("vat_code"):
        return None
    item: dict[str, object] = {
        "description": f"Subscription plan #{order.plan_id}, {order.duration_days}d",
        "quantity": "1.00",
        "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
        "vat_code": int(settings["vat_code"]),
    }
    return {"customer": {"email": order.customer_email}, "items": [item]}


# Docs: https://yookassa.ru/developers
class YooKassaGateway(PaymentGateway):
    currency = Currency.RUB

    @classmethod
    def requires_customer_email(cls, settings: dict[str, str]) -> bool:
        return bool(settings.get("vat_code"))

    def _auth(self) -> tuple[str, str]:
        return self._require("shop_id"), self._require("api_key")

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        body: dict[str, object] = {
            "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
            "confirmation": {"type": "redirect", "return_url": self._return_url},
            "capture": True,
            "description": f"Order #{order.id}",
            "metadata": {"order_ref": order.idempotency_key},
        }
        receipt = _build_receipt(order, self._settings)
        if receipt is not None:
            body["receipt"] = receipt

        response = await http_client.post(
            f"{_API_BASE}/payments",
            json=body,
            auth=self._auth(),
            headers={"Idempotence-Key": order.idempotency_key},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return PaymentIntent(
            confirmation_url=str(data["confirmation"]["confirmation_url"]),
            provider_payment_id=str(data["id"]),
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # YooKassa does not sign notifications; fetch_payment is the check.
        payload = parse_json(request.body, "YooKassa")
        obj = payload.get("object")
        if not isinstance(obj, dict):
            raise PaymentGatewayError("Malformed YooKassa webhook")
        event = str(payload.get("event"))
        metadata = obj.get("metadata") or {}
        # a refund object carries its payment under payment_id; its own id is the refund's
        payment_id = (
            obj.get("payment_id") if event.startswith(_REFUND_EVENT_PREFIX) else obj.get("id")
        )
        return WebhookSignal(
            reference=str(metadata.get("order_ref", "")),
            claims_paid=event == _PAID_EVENT,
            provider_payment_id=str(payment_id) if payment_id else None,
            reported_status=_REPORTED_EVENTS.get(event),
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await http_client.get(
            f"{_API_BASE}/payments/{order.external_payment_id}",
            auth=self._auth(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        amount = data.get("amount") or {}
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS and data.get("paid") is True,
            amount=to_decimal(amount.get("value")),
            currency=amount.get("currency"),
            reference=str((data.get("metadata") or {}).get("order_ref") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
        )
