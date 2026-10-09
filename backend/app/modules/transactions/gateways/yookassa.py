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
    WebhookRequest,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import PROVIDER_API_TIMEOUT_S, parse_json, to_decimal

_API_BASE: Final[str] = "https://api.yookassa.ru/v3"
_PAID_STATUS: Final[str] = "succeeded"
_PAID_EVENT: Final[str] = "payment.succeeded"
_REPORTED_EVENTS: Final[dict[str, TransactionStatus]] = {
    "payment.canceled": TransactionStatus.CANCELED,
    "refund.succeeded": TransactionStatus.REFUNDED,
}
_REFUND_EVENT_PREFIX: Final[str] = "refund."


def _build_receipt(order: TransactionDto, settings: dict[str, str]) -> Optional[dict[str, object]]:
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
    # https://yookassa.ru/developers/using-api/webhooks#ip
    trusted_networks = (
        "77.75.153.0/25",
        "77.75.156.11/32",
        "77.75.156.35/32",
        "77.75.154.128/25",
        "185.71.76.0/27",
        "185.71.77.0/27",
        "2a02:5180:0:1509::/64",
        "2a02:5180:0:2655::/64",
        "2a02:5180:0:1533::/64",
        "2a02:5180:0:2669::/64",
    )

    @classmethod
    def requires_customer_email(cls, settings: dict[str, str]) -> bool:
        return bool(settings.get("vat_code"))

    def _auth(self) -> tuple[str, str]:
        return self._require("shop_id"), self._require("api_key")

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
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

        response = await self._http.post(
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
        refund_amount = obj.get("amount") if event.startswith(_REFUND_EVENT_PREFIX) else None
        refund_amount = refund_amount if isinstance(refund_amount, dict) else {}
        return WebhookSignal(
            reference=str(metadata.get("order_ref", "")),
            claims_paid=event == _PAID_EVENT,
            provider_payment_id=str(payment_id) if payment_id else None,
            reported_status=_REPORTED_EVENTS.get(event),
            refund_amount=to_decimal(refund_amount.get("value")),
            refund_currency=refund_amount.get("currency"),
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
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
