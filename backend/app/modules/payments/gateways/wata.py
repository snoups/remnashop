from time import monotonic
from typing import Final, Optional

import orjson
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
    http_client,
)
from app.modules.payments.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    format_utc,
    link_expiry,
    load_rsa_public_key,
    parse_json,
    rsa_verify,
    to_decimal,
)

_API_BASE: Final[str] = "https://api.wata.pro/api/h2h"
_PUBLIC_KEY_TTL_S: Final[float] = 3600.0
# WATA rejects expirationDateTime <= now + 10 minutes.
_MIN_LINK_LIFETIME_S: Final[int] = 11 * 60
_PAID_STATUS: Final[str] = "Paid"
_PAYMENT_KIND: Final[str] = "Payment"

# Keyed by api_key, not per instance: the factory builds a fresh gateway for
# every request, so an instance-level cache would never be reused.
_public_key_cache: Final[dict[str, tuple[float, RSAPublicKey]]] = {}


def clear_public_key_cache() -> None:
    _public_key_cache.clear()


class WataGateway(PaymentGateway):
    currency = Currency.USD

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._require('api_key')}"}

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "type": "OneTime",
            "amount": amount_to_float(order.final_price),
            "currency": order.currency.value,
            "description": f"Order #{order.id}",
            "orderId": order.idempotency_key,
            "successRedirectUrl": self._return_url,
            "failRedirectUrl": self._return_url,
            "expirationDateTime": format_utc(
                link_expiry(order, minimum_seconds=_MIN_LINK_LIFETIME_S)
            ),
        }
        response = await http_client.post(
            f"{_API_BASE}/links", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        payment_url = orjson.loads(response.content).get("url")
        if not payment_url:
            raise PaymentGatewayError("WATA response missing 'url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("x-signature", "")
        if not signature:
            raise PaymentGatewayError("WATA webhook missing X-Signature header")
        public_key = await self._public_key()
        if not rsa_verify(public_key, signature, request.body, hashes.SHA512()):
            raise PaymentGatewayError("Invalid WATA webhook signature")

        data = parse_json(request.body, "WATA")
        order_ref = data.get("orderId")
        if not order_ref:
            raise PaymentGatewayError("WATA webhook missing 'orderId'")
        transaction_id = data.get("transactionId")
        # A completed refund also reports transactionStatus=Paid.
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=data.get("kind") == _PAYMENT_KIND
            and data.get("transactionStatus") == _PAID_STATUS,
            provider_payment_id=str(transaction_id) if transaction_id else None,
        )

    async def fetch_payment(self, order: PaymentOrderDto, signal: WebhookSignal) -> ProviderPayment:
        if not signal.provider_payment_id:
            return NOT_PAID
        response = await http_client.get(
            f"{_API_BASE}/transactions/{signal.provider_payment_id}",
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS and data.get("kind") == _PAYMENT_KIND,
            amount=to_decimal(data.get("amount")),
            currency=data.get("currency"),
            reference=str(data.get("orderId") or ""),
            provider_payment_id=str(data.get("id") or signal.provider_payment_id),
        )

    async def _public_key(self) -> RSAPublicKey:
        api_key = self._require("api_key")
        cached = _public_key_cache.get(api_key)
        if cached is not None and cached[0] > monotonic():
            return cached[1]

        response = await http_client.get(
            f"{_API_BASE}/public-key", headers=self._headers(), timeout=PROVIDER_API_TIMEOUT_S
        )
        response.raise_for_status()
        key = load_rsa_public_key(orjson.loads(response.content)["value"])
        _public_key_cache[api_key] = (monotonic() + _PUBLIC_KEY_TTL_S, key)
        return key
