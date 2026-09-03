from typing import Final, Optional

import httpx
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

_API_BASE: Final[str] = "https://api.yookassa.ru/v3"
_TIMEOUT_S: Final[float] = 15.0

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)

_STATUS_MAP: Final[dict[str, PaymentOrderStatus]] = {
    "succeeded": PaymentOrderStatus.PAID,
}


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


class YooKassaGateway(PaymentGateway):
    currency = Currency.RUB

    def _auth(self) -> tuple[str, str]:
        return self._settings["shop_id"], self._settings["api_key"]

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

        response = await _client.post(
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

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            payload = orjson.loads(request.body)
            obj = payload["object"]
            status = _STATUS_MAP.get(str(obj.get("status")))
        except (orjson.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
            raise PaymentGatewayError("Malformed YooKassa webhook") from error

        if status is None:
            return None

        metadata = obj.get("metadata") or {}
        return WebhookResult(
            reference=str(metadata.get("order_ref", "")),
            status=status,
            provider_payment_id=str(obj["id"]) if obj.get("id") else None,
        )

    async def verify_payment(self, order: PaymentOrderDto) -> bool:
        if not order.external_payment_id:
            return False
        response = await _client.get(
            f"{_API_BASE}/payments/{order.external_payment_id}", auth=self._auth()
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return bool(data.get("status") == "succeeded")
