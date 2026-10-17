import uuid
from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    compact_json,
    hmac_hex,
    link_lifetime,
    parse_json,
    safe_equals,
    signing_json,
    to_decimal,
)

_API_BASE: Final[str] = "https://severpay.io/api/merchant"
_PAID_STATUS: Final[str] = "success"
_REPORTED_STATUSES: Final[frozenset[str]] = frozenset({"decline", "fail"})
_PAYIN_TYPE: Final[str] = "payin"
_MIN_LIFETIME_MINUTES: Final[int] = 30
_MAX_LIFETIME_MINUTES: Final[int] = 4320


# Docs: https://docs.severpay.io/en/
class SeverPayGateway(PaymentGateway):
    currency = Currency.RUB
    ack = WebhookAck(body='{"status": true}', media_type="application/json")

    def _signed(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {**payload, "mid": int(self._require("mid")), "salt": uuid.uuid4().hex}
        ordered = dict(sorted(body.items()))
        return {**ordered, "sign": hmac_hex(self._require("token"), compact_json(ordered))}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = self._signed(
            {
                "order_id": order.idempotency_key,
                "amount": amount_to_float(order.final_price),
                "currency": order.currency.value,
                "client_email": order.customer_email or f"user{order.user_id}@vpn.local",
                "client_id": str(order.user_id),
                "url_return": self._return_url,
                "lifetime": link_lifetime(
                    order,
                    unit="minutes",
                    minimum=_MIN_LIFETIME_MINUTES,
                    maximum=_MAX_LIFETIME_MINUTES,
                ),
            }
        )
        response = await self._http.post(f"{_API_BASE}/payin/create", json=payload)
        response.raise_for_status()
        data = orjson.loads(response.content)
        if data.get("status") is not True:
            raise PaymentGatewayError(f"SeverPay API error: {data.get('msg') or data}")

        result = data.get("data") or {}
        payment_url = result.get("url")
        if not payment_url:
            raise PaymentGatewayError("SeverPay response missing 'url'")
        payment_id = result.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = parse_json(request.body, "SeverPay")
        received_sign = data.pop("sign", None)
        if not received_sign or not self._webhook_signature_valid(data, str(received_sign)):
            raise PaymentGatewayError("Invalid SeverPay webhook signature")

        if data.get("type") != _PAYIN_TYPE:
            return None
        payin = data.get("data") or {}
        payment_id = payin.get("id")
        if not payment_id:
            raise PaymentGatewayError("SeverPay webhook missing 'data.id'")
        return WebhookSignal(
            reference=str(payin.get("order_id") or ""),
            claims_paid=payin.get("status") == _PAID_STATUS,
            provider_payment_id=str(payment_id),
            reported_status=TransactionStatus.FAILED
            if payin.get("status") in _REPORTED_STATUSES
            else None,
        )

    def _webhook_signature_valid(self, data: dict[str, Any], received: str) -> bool:
        # The docs' PHP handler hashes json_encode() output (escaped "/" and
        # non-ASCII); their Python sample hashes unescaped JSON.
        token = self._require("token")
        candidates = (signing_json(data, escape_unicode=True), compact_json(data))
        return any(
            safe_equals(hmac_hex(token, candidate), received, ignore_case=True)
            for candidate in candidates
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        payload = self._signed({"id": int(order.external_payment_id)})
        response = await self._http.post(
            f"{_API_BASE}/payin/get", json=payload, timeout=PROVIDER_API_TIMEOUT_S
        )
        response.raise_for_status()
        result = orjson.loads(response.content)
        if result.get("status") is not True:
            return NOT_PAID
        payin = result.get("data") or {}
        return ProviderPayment(
            paid=payin.get("status") == _PAID_STATUS,
            amount=to_decimal(payin.get("amount")),
            currency=payin.get("currency"),
            reference=str(payin.get("order_id") or ""),
            provider_payment_id=str(payin.get("id") or order.external_payment_id),
        )
