import time
from typing import Any, Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookRequest,
    WebhookSignal,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    md5_hex,
    parse_form,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.fk.life/v1"
_PAID_ORDER_STATUS: Final[str] = "1"


class FreeKassaGateway(PaymentGateway):
    currency = Currency.RUB
    ack = WebhookAck(body="YES")

    def _signed(self, params: dict[str, Any]) -> dict[str, Any]:
        joined = "|".join(str(value) for _, value in sorted(params.items()))
        signature = hmac_hex(self._require("api_key"), joined.encode("utf-8"))
        return {**params, "signature": signature}

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        email = (
            self._optional("customer_email")
            or order.customer_email
            or f"user_{order.idempotency_key}@telegram.org"
        )
        data = self._signed(
            {
                "shopId": int(self._require("shop_id")),
                "nonce": time.time_ns(),
                "paymentId": order.idempotency_key,
                "i": int(self._require("payment_system_id")),
                "email": email,
                "ip": self._require("customer_ip"),
                "amount": f"{order.final_price:.2f}",
                "currency": order.currency.value,
                "success_url": self._return_url,
                "failure_url": self._return_url,
                "notification_url": self._webhook_url,
            }
        )
        response = await http_client.post(f"{_API_BASE}/orders/create", json=data)
        response.raise_for_status()
        result = orjson.loads(response.content)
        if result.get("type") != "success":
            raise PaymentGatewayError(f"FreeKassa API error: {result}")

        payment_url = result.get("location")
        if not payment_url:
            raise PaymentGatewayError("FreeKassa response missing 'location'")
        order_id = result.get("orderId")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(order_id) if order_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = parse_form(request.body, "FreeKassa")
        merchant_id = data.get("MERCHANT_ID", "")
        if merchant_id != self._require("shop_id"):
            raise PaymentGatewayError("FreeKassa webhook MERCHANT_ID does not match shop_id")

        order_ref = data.get("MERCHANT_ORDER_ID")
        if not order_ref:
            raise PaymentGatewayError("FreeKassa webhook missing 'MERCHANT_ORDER_ID'")

        raw = f"{merchant_id}:{data.get('AMOUNT', '')}:{self._require('secret_word_2')}:{order_ref}"
        if not safe_equals(md5_hex(raw), data.get("SIGN", ""), ignore_case=True):
            raise PaymentGatewayError("Invalid FreeKassa webhook signature")

        # FreeKassa notifies only about successful payments.
        return WebhookSignal(
            reference=order_ref, claims_paid=True, provider_payment_id=data.get("intid") or None
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        params = self._signed(
            {
                "shopId": int(self._require("shop_id")),
                "nonce": time.time_ns(),
                "paymentId": order.idempotency_key,
            }
        )
        response = await http_client.post(
            f"{_API_BASE}/orders", json=params, timeout=PROVIDER_API_TIMEOUT_S
        )
        response.raise_for_status()
        orders = orjson.loads(response.content).get("orders") or []
        match = next(
            (
                item
                for item in orders
                if str(item.get("merchant_order_id")) == order.idempotency_key
            ),
            None,
        )
        if match is None:
            return NOT_PAID
        fk_order_id = match.get("fk_order_id")
        return ProviderPayment(
            paid=str(match.get("status")) == _PAID_ORDER_STATUS,
            amount=to_decimal(match.get("amount")),
            currency=match.get("currency"),
            reference=str(match.get("merchant_order_id")),
            provider_payment_id=str(fk_order_id) if fk_order_id else None,
        )
