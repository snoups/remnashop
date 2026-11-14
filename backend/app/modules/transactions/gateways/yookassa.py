from dataclasses import replace
from typing import Final, Optional
from urllib.parse import quote

import orjson

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.gateways import YooKassaSettings
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import PROVIDER_API_TIMEOUT_S, parse_json, to_decimal

_API_BASE: Final[str] = "https://api.yookassa.ru/v3"
_PAID_STATUS: Final[str] = "succeeded"
_CANCELED_STATUS: Final[str] = "canceled"
_PAID_EVENT: Final[str] = "payment.succeeded"
_REPORTED_EVENTS: Final[dict[str, TransactionStatus]] = {
    "payment.canceled": TransactionStatus.CANCELED,
    "refund.succeeded": TransactionStatus.REFUNDED,
}
_REFUND_EVENT_PREFIX: Final[str] = "refund."
_PAYMENT_SUBJECT: Final[str] = "service"
_PAYMENT_MODE: Final[str] = "full_payment"


def _build_receipt(
    order: TransactionDto, settings: YooKassaSettings
) -> Optional[dict[str, object]]:
    vat_code = order.yookassa_receipt_vat_code if order.is_recurring else settings.vat_code
    if not order.customer_email or vat_code is None:
        return None
    item: dict[str, object] = {
        "description": f"Subscription plan #{order.plan_id}, {order.duration_days}d",
        "quantity": "1.00",
        "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
        "vat_code": int(vat_code),
        "payment_subject": _PAYMENT_SUBJECT,
        "payment_mode": _PAYMENT_MODE,
    }
    return {"customer": {"email": order.customer_email}, "items": [item]}


# Docs: https://yookassa.ru/developers
class YooKassaGateway(PaymentGateway[YooKassaSettings]):
    settings_model = YooKassaSettings
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
        # asked before checkout checks the form is complete, so an incomplete one is no receipt
        try:
            return YooKassaSettings.from_values(settings).vat_code is not None
        except PaymentGatewayError:
            return False

    def _auth(self) -> tuple[str, str]:
        return self.settings.shop_id, self.settings.api_key.get_secret_value()

    @staticmethod
    def payment_matches(order: TransactionDto, payment: ProviderPayment) -> bool:
        return (
            payment.amount == order.final_price
            and payment.currency == order.currency.value
            and PaymentGateway.payment_matches(order, payment)
        )

    def _payment_body(self, order: TransactionDto) -> dict[str, object]:
        body: dict[str, object] = {
            "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
            "capture": True,
            "description": f"Order #{order.id}",
            "metadata": {"order_ref": order.idempotency_key},
        }
        receipt = _build_receipt(order, self.settings)
        if receipt is not None:
            body["receipt"] = receipt
        return body

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        body = self._payment_body(order)
        body["confirmation"] = {"type": "redirect", "return_url": self._return_url}
        # Explicit false also suppresses YooKassa's conditional-save checkbox.
        body["save_payment_method"] = (
            self.settings.recurring_enabled and order.recurring_consent and not order.is_test
        )

        data = await self._post_payment(order, body)
        return PaymentIntent(
            confirmation_url=str(data["confirmation"]["confirmation_url"]),
            provider_payment_id=str(data["id"]),
        )

    async def create_recurring_payment(
        self, order: TransactionDto, payment_method_id: str
    ) -> PaymentIntent:
        if not self.settings.recurring_enabled or not order.is_recurring or not payment_method_id:
            raise PaymentGatewayError("Recurring payments are not enabled for this order")
        body = self._payment_body(order)
        body["payment_method_id"] = payment_method_id
        data = await self._post_payment(order, body)
        return PaymentIntent(confirmation_url=None, provider_payment_id=str(data["id"]))

    async def _post_payment(self, order: TransactionDto, body: dict[str, object]) -> dict:
        response = await self._http.post(
            f"{_API_BASE}/payments",
            json=body,
            auth=self._auth(),
            headers={"Idempotence-Key": order.idempotency_key},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]:
            raise PaymentGatewayError("YooKassa returned no payment ID")
        return data

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
        # A callback may beat the create response, or the response may be lost.
        # The callback ID is only a lookup hint: confirm still checks the API's
        # order reference, amount, currency and paid status before crediting it.
        payment_id = order.external_payment_id or signal.provider_payment_id
        if not payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{_API_BASE}/payments/{quote(payment_id, safe='')}",
            auth=self._auth(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if data.get("id") != payment_id:
            raise PaymentGatewayError("YooKassa returned a different payment ID")
        amount = data.get("amount") or {}
        method = data.get("payment_method") or {}
        if not isinstance(amount, dict) or not isinstance(method, dict):
            raise PaymentGatewayError("YooKassa returned malformed payment data")
        paid_amount = to_decimal(amount.get("value"))
        currency = amount.get("currency")
        if paid_amount is None or not isinstance(currency, str):
            raise PaymentGatewayError("YooKassa returned no valid amount or currency")
        method_id = method.get("id")
        saved_method = (
            method_id
            if method.get("saved") is True
            and isinstance(method_id, str)
            and 0 < len(method_id) <= 128
            else None
        )
        cancellation = data.get("cancellation_details")
        reason = cancellation.get("reason") if isinstance(cancellation, dict) else None
        return ProviderPayment(
            cancellation_reason=reason if isinstance(reason, str) and len(reason) <= 64 else None,
            paid=data.get("status") == _PAID_STATUS and data.get("paid") is True,
            amount=paid_amount,
            currency=currency,
            reference=str((data.get("metadata") or {}).get("order_ref") or ""),
            provider_payment_id=str(data.get("id") or order.external_payment_id),
            saved_payment_method_id=saved_method,
            payment_method_shop_id=self.settings.shop_id if saved_method else None,
            status={
                _PAID_STATUS: TransactionStatus.PAID,
                _CANCELED_STATUS: TransactionStatus.CANCELED,
            }.get(data.get("status"), TransactionStatus.PENDING),
        )

    async def confirm_reported(
        self, order: TransactionDto, signal: WebhookSignal
    ) -> Optional[WebhookSignal]:
        # Cancellation callbacks can also recover the ID lost with the create response.
        if signal.reported_status is TransactionStatus.CANCELED:
            payment = await self.fetch_payment(order, signal)
            if (
                payment.status is not TransactionStatus.CANCELED
                or payment.reference != order.idempotency_key
                or payment.amount != order.final_price
                or payment.currency != order.currency.value
            ):
                return None
            return replace(
                signal,
                provider_payment_id=payment.provider_payment_id,
                cancellation_reason=payment.cancellation_reason,
            )
        # Notifications are unsigned; a refund claws back referral rewards.
        if not order.external_payment_id:
            return None
        response = await self._http.get(
            f"{_API_BASE}/payments/{order.external_payment_id}",
            auth=self._auth(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if signal.reported_status is TransactionStatus.REFUNDED:
            refunded = data.get("refunded_amount") or {}
            amount = to_decimal(refunded.get("value"))
            if not amount:
                return None
            return replace(signal, refund_amount=amount, refund_currency=refunded.get("currency"))
        return None
