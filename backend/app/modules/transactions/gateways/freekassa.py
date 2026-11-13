import asyncio
import socket
import time
from typing import Any, Final, Optional
from urllib.parse import urlsplit

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.gateways import FreeKassaSettings
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    md5_hex,
    parse_form,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.fk.life/v1"
_PAID_ORDER_STATUS: Final[str] = "1"
# The API insists on an `ip`; it's this server's, not the buyer's (the checkout
# request doesn't carry one). Last resort if the domain doesn't resolve.
_FALLBACK_SERVER_IP: Final[str] = "127.0.0.1"


_SERVER_IP_TTL_S: Final[float] = 300.0
_server_ip_cache: Final[dict[str, tuple[str, float]]] = {}


async def _resolve_server_ip(webhook_url: str) -> str:
    host = urlsplit(webhook_url).hostname
    if host is None:
        return _FALLBACK_SERVER_IP
    cached = _server_ip_cache.get(host)
    if cached is not None and cached[1] > time.monotonic():
        return cached[0]
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, family=socket.AF_INET)
    except OSError:
        return _FALLBACK_SERVER_IP
    ip = str(infos[0][4][0])
    _server_ip_cache[host] = (ip, time.monotonic() + _SERVER_IP_TTL_S)
    return ip


# Docs: https://docs.freekassa.net/
class FreeKassaGateway(PaymentGateway[FreeKassaSettings]):
    settings_model = FreeKassaSettings
    currency = Currency.RUB
    ack = WebhookAck(body="YES")

    @classmethod
    def requires_customer_email(cls, settings: dict[str, str]) -> bool:
        return True

    def _signed(self, params: dict[str, Any]) -> dict[str, Any]:
        joined = "|".join(str(value) for _, value in sorted(params.items()))
        signature = hmac_hex(self.settings.api_key.get_secret_value(), joined.encode("utf-8"))
        return {**params, "signature": signature}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        data = self._signed(
            {
                "shopId": int(self.settings.shop_id),
                "nonce": time.time_ns(),
                "paymentId": order.idempotency_key,
                "i": int(self.settings.payment_system_id),
                "email": order.customer_email,
                "ip": await _resolve_server_ip(self._webhook_url),
                "amount": f"{order.final_price:.2f}",
                "currency": order.currency.value,
                "success_url": self._return_url,
                "failure_url": self._return_url,
                "notification_url": self._webhook_url,
            }
        )
        response = await self._http.post(f"{_API_BASE}/orders/create", json=data)
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
        if merchant_id != self.settings.shop_id:
            raise PaymentGatewayError("FreeKassa webhook MERCHANT_ID does not match shop_id")

        order_ref = data.get("MERCHANT_ORDER_ID")
        if not order_ref:
            raise PaymentGatewayError("FreeKassa webhook missing 'MERCHANT_ORDER_ID'")

        secret = self.settings.secret_word_2.get_secret_value()
        raw = f"{merchant_id}:{data.get('AMOUNT', '')}:{secret}:{order_ref}"
        if not safe_equals(md5_hex(raw), data.get("SIGN", ""), ignore_case=True):
            raise PaymentGatewayError("Invalid FreeKassa webhook signature")

        # FreeKassa notifies only about successful payments.
        return WebhookSignal(
            reference=order_ref, claims_paid=True, provider_payment_id=data.get("intid") or None
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        params = self._signed(
            {
                "shopId": int(self.settings.shop_id),
                "nonce": time.time_ns(),
                "paymentId": order.idempotency_key,
            }
        )
        response = await self._http.post(
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
