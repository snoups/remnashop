from typing import Final, Optional

import httpx
import orjson

from app.modules.payments.dto import PaymentOrderDto

_API_BASE: Final[str] = "https://api.yookassa.ru/v3"
_TIMEOUT_S: Final[float] = 15.0
# Placeholder pending the bot-UI design (spec §9).
_YOOKASSA_RETURN_URL: Final[str] = "https://t.me"

# Module-level, not per-call: reuses one connection pool across every
# YooKassaGateway() instance instead of a fresh TLS handshake per request.
# auth is passed per-call below (shop credentials vary per admin/shop), not
# fixed at client construction. Never explicitly closed -- process-lifetime,
# same as RemnawaveProvider's client but without a DI shutdown hook since
# this gateway isn't itself DI-provided.
_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


def _build_receipt(order: PaymentOrderDto, settings: dict[str, str]) -> Optional[dict[str, object]]:
    # YooKassa's receipt schema requires vat_code on every item -- sending a
    # receipt without it is a 400, so no receipt at all is the working path.
    if not order.customer_email or not settings.get("vat_code"):
        return None
    item: dict[str, object] = {
        "description": f"Subscription plan #{order.plan_id}, {order.duration_days}d",
        "quantity": "1.00",
        "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
        "vat_code": int(settings["vat_code"]),
    }
    return {"customer": {"email": order.customer_email}, "items": [item]}


class YooKassaGateway:
    async def create_payment(
        self, order: PaymentOrderDto, settings: dict[str, str]
    ) -> tuple[str, str]:
        body: dict[str, object] = {
            "amount": {"value": f"{order.final_price:.2f}", "currency": order.currency.value},
            "confirmation": {"type": "redirect", "return_url": _YOOKASSA_RETURN_URL},
            "capture": True,
            "description": f"Order #{order.id}",
        }
        receipt = _build_receipt(order, settings)
        if receipt is not None:
            body["receipt"] = receipt

        response = await _client.post(
            f"{_API_BASE}/payments",
            json=body,
            auth=(settings["shop_id"], settings["api_key"]),
            headers={"Idempotence-Key": order.idempotency_key},
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return str(data["id"]), str(data["confirmation"]["confirmation_url"])

    async def verify_payment(self, external_payment_id: str, settings: dict[str, str]) -> bool:
        response = await _client.get(
            f"{_API_BASE}/payments/{external_payment_id}",
            auth=(settings["shop_id"], settings["api_key"]),
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return bool(data.get("status") == "succeeded")
