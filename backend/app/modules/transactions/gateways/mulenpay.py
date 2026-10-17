import hashlib
from typing import ClassVar, Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import PROVIDER_API_TIMEOUT_S, parse_json, to_decimal

_PAYMENT_SUBJECT: Final[int] = 4
_PAYMENT_MODE: Final[int] = 4
_DEFAULT_VAT_CODE: Final[int] = 0
_PAID_STATUS_CODE: Final[int] = 3
_PAID_CALLBACK_STATUS: Final[str] = "success"


# Docs: https://docs.mulenpay.com/
class MulenPayGateway(PaymentGateway):
    currency = Currency.RUB
    API_BASE: ClassVar[str] = "https://mulenpay.ru/api"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._require('api_key')}"}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        currency = order.currency.value.lower()
        amount = f"{order.final_price:.2f}"
        shop_id = int(self._require("shop_id"))
        vat_code = self._optional("vat_code")
        payload: dict[str, object] = {
            "currency": currency,
            "amount": amount,
            "uuid": order.idempotency_key,
            "shopId": shop_id,
            "description": f"Order #{order.id}",
            "sign": self._sign(currency, amount, shop_id),
            "website_url": self._return_url,
            "items": [
                {
                    "description": f"Order #{order.id}",
                    "quantity": 1,
                    "price": float(amount),
                    "vat_code": int(vat_code) if vat_code else _DEFAULT_VAT_CODE,
                    "payment_subject": _PAYMENT_SUBJECT,
                    "payment_mode": _PAYMENT_MODE,
                }
            ],
        }
        if order.customer_email:
            # Without it the receipt goes to the shop owner's email.
            payload["client"] = order.customer_email
        response = await self._http.post(
            f"{self.API_BASE}/v2/payments", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("success"):
            raise PaymentGatewayError(f"{type(self).__name__} API error: {data}")

        payment_url = data.get("paymentUrl")
        payment_id = data.get("id")
        if not payment_url or payment_id is None:
            raise PaymentGatewayError(f"{type(self).__name__} response missing 'paymentUrl'/'id'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=str(payment_id))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # The callback carries no documented authentication; fetch_payment is
        # the check.
        data = parse_json(request.body, type(self).__name__)
        order_ref = data.get("uuid")
        if not order_ref:
            raise PaymentGatewayError(f"{type(self).__name__} webhook missing 'uuid'")
        payment_id = data.get("id")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=data.get("payment_status") == _PAID_CALLBACK_STATUS,
            provider_payment_id=str(payment_id) if payment_id is not None else None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{self.API_BASE}/v2/payments/{order.external_payment_id}",
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        payment = orjson.loads(response.content).get("payment") or {}
        return ProviderPayment(
            paid=payment.get("status") == _PAID_STATUS_CODE,
            amount=to_decimal(payment.get("amount")),
            currency=payment.get("currency"),
            reference=str(payment.get("uuid") or ""),
            provider_payment_id=str(payment.get("id") or order.external_payment_id),
        )

    def _sign(self, currency: str, amount: str, shop_id: int) -> str:
        raw = f"{currency}{amount}{shop_id}{self._require('secret_key')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
