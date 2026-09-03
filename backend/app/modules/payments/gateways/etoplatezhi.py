import base64
import hashlib
import hmac
from typing import Final, Optional
from urllib.parse import urlencode

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

_PAYMENT_PAGE_URL: Final[str] = "https://paymentpage.etoplatezhi.ru/payment"
_IGNORED_KEYS: Final[frozenset[str]] = frozenset({"frame_mode", "signature"})


def _flatten_list(key: str, items: list[object]) -> list[str]:
    entries: list[str] = []
    for index, item in enumerate(items):
        item_key = f"{key}:{index}"
        if isinstance(item, dict):
            entries.extend(_flatten(item, item_key))
        elif isinstance(item, bool):
            entries.append(f"{item_key}:{'1' if item else '0'}")
        elif item is not None:
            entries.append(f"{item_key}:{item}")
    return entries


def _flatten(params: dict[str, object], prefix: str = "") -> list[str]:
    entries: list[str] = []
    for key, value in params.items():
        if key in _IGNORED_KEYS:
            continue
        full_key = f"{prefix}:{key}" if prefix else key
        if isinstance(value, dict):
            entries.extend(_flatten(value, full_key))
        elif isinstance(value, list):
            entries.extend(_flatten_list(full_key, value))
        elif isinstance(value, bool):
            entries.append(f"{full_key}:{'1' if value else '0'}")
        elif value is not None:
            entries.append(f"{full_key}:{value}")
    return entries


def _strip_signature(data: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in data.items():
        if key == "signature":
            continue
        result[key] = _strip_signature(value) if isinstance(value, dict) else value
    return result


class EtoplatezhiGateway(PaymentGateway):
    currency = Currency.RUB

    def _sign(self, params: dict[str, object]) -> str:
        entries = sorted(_flatten(params))
        message = ";".join(entries)
        digest = hmac.new(
            self._settings["secret_key"].encode("utf-8"), message.encode("utf-8"), hashlib.sha512
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        # Etoplatezhi is a redirect-to-hosted-page gateway -- no create API
        # call, just a signed URL built client-side.
        params: dict[str, object] = {
            "project_id": int(self._settings["project_id"]),
            "payment_id": order.idempotency_key,
            "payment_amount": int(order.final_price * 100),
            "payment_currency": order.currency.value,
            "customer_id": str(order.user_id),
            "payment_description": f"Order #{order.id}",
            "merchant_callback_url": self._webhook_url,
            "redirect_success_url": self._return_url,
            "redirect_fail_url": self._return_url,
        }
        params["signature"] = self._sign(params)
        return PaymentIntent(
            confirmation_url=f"{_PAYMENT_PAGE_URL}?{urlencode(params)}", provider_payment_id=None
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            payload = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Etoplatezhi webhook") from error

        received_sign = payload.get("signature")
        if not received_sign:
            raise PaymentGatewayError("Etoplatezhi webhook missing 'signature'")
        if not hmac.compare_digest(self._sign(_strip_signature(payload)), str(received_sign)):
            raise PaymentGatewayError("Invalid Etoplatezhi webhook signature")

        payment = payload.get("payment", {})
        # payment.id in the callback echoes the payment_id WE sent when
        # building the redirect URL -- it is our own order reference.
        order_ref = payment.get("id")
        status = payment.get("status")
        if not order_ref or not status:
            raise PaymentGatewayError("Etoplatezhi webhook missing 'payment.id'/'payment.status'")

        if status != "success":
            return None
        return WebhookResult(reference=str(order_ref), status=PaymentOrderStatus.PAID)
