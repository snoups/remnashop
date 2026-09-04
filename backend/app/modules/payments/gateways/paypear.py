import hashlib
import hmac
import json
import uuid
from base64 import b64encode
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
    http_client,
    ip_in_networks,
)

_API_BASE: Final[str] = "https://api.paypear.ru/v1"
_DEFAULT_PAYMENT_METHOD: Final[str] = "sbp"


class PayPearGateway(PaymentGateway):
    currency = Currency.RUB
    # Documented webhook source IP -- PayPear's own docs don't specify a
    # signature algorithm, so this is the fallback verification path.
    trusted_networks = ("158.160.85.101/32",)

    def _basic_auth(self) -> str:
        credentials = f"{self._require('shop_id')}:{self._require('secret_key')}"
        return "Basic " + b64encode(credentials.encode("utf-8")).decode("utf-8")

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
            "order_id": order.idempotency_key,
            "payment_method_data": {"type": _DEFAULT_PAYMENT_METHOD},
            "description": f"Order #{order.id}",
            "confirmation": {"type": "redirect", "return_url": self._return_url},
            "webhook_url": self._webhook_url,
        }
        response = await http_client.post(
            f"{_API_BASE}/payment/",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": self._basic_auth(),
                "Idempotence-Key": uuid.uuid4().hex,
            },
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if data.get("success") is not True:
            raise PaymentGatewayError(f"PayPear API error: {data.get('message') or data}")

        result = data.get("result", {})
        confirmation = result.get("confirmation") or {}
        payment_url = confirmation.get("confirmation_url") or confirmation.get("url")
        if not payment_url:
            raise PaymentGatewayError("PayPear response missing a confirmation URL")
        payment_id = result.get("id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            payload = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed PayPear webhook") from error

        if not self._verified(payload, request.client_ip):
            raise PaymentGatewayError("PayPear webhook failed signature and IP verification")

        obj = payload.get("object", {})
        payment_id = obj.get("id")
        if not payment_id or not obj.get("status"):
            raise PaymentGatewayError("PayPear webhook missing 'id'/'status'")

        is_confirmed = (
            payload.get("event") == "payment.confirmed" or obj.get("status") == "CONFIRMED"
        )
        if not is_confirmed:
            return None

        order_ref = obj.get("order_id")
        return WebhookResult(
            reference=str(order_ref) if order_ref else "",
            status=PaymentOrderStatus.PAID,
            provider_payment_id=str(payment_id),
        )

    def _verified(self, payload: dict[str, object], client_ip: Optional[str]) -> bool:
        signature = payload.get("signature")
        secret = self._optional("secret_key")
        if signature and secret:
            without_sig = {key: value for key, value in payload.items() if key != "signature"}
            for body_to_sign in (
                json.dumps(without_sig, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                json.dumps(without_sig, separators=(",", ":")).encode("utf-8"),
            ):
                expected = hmac.new(
                    secret.encode("utf-8"), body_to_sign, hashlib.sha256
                ).hexdigest()
                if hmac.compare_digest(expected, str(signature)):
                    return True
        return ip_in_networks(client_ip or "", self.trusted_networks)
