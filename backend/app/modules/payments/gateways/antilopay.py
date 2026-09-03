import base64
import json
from typing import Final, Optional

import httpx
import orjson
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
)

_API_BASE: Final[str] = "https://lk.antilopay.com/api/v2"
_TIMEOUT_S: Final[float] = 20.0

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class AntilopayGateway(PaymentGateway):
    currency = Currency.RUB

    def _private_key(self) -> RSAPrivateKey:
        der = base64.b64decode(self._settings["private_key"])
        key = serialization.load_der_private_key(der, password=None)
        if not isinstance(key, RSAPrivateKey):
            raise PaymentGatewayError("Antilopay private key is not an RSA key")
        return key

    def _public_key(self) -> RSAPublicKey:
        der = base64.b64decode(self._settings["public_key"])
        key = serialization.load_der_public_key(der)
        if not isinstance(key, RSAPublicKey):
            raise PaymentGatewayError("Antilopay public key is not an RSA key")
        return key

    def _sign(self, body: bytes) -> str:
        signature = self._private_key().sign(body, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode()

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "project_identificator": self._settings["project_id"],
            "amount": float(order.final_price),
            "order_id": order.idempotency_key,
            "currency": order.currency.value.lower(),
            "product_name": f"Order #{order.id}",
            "product_type": "services",
            "description": f"Order #{order.id}",
            "customer": {"email": order.customer_email or "user@vpn.bot"},
            "success_url": self._return_url,
            "fail_url": self._return_url,
        }
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        response = await _client.post(
            f"{_API_BASE}/payment/create",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Apay-Secret-Id": self._settings["secret_id"],
                "X-Apay-Sign": self._sign(body),
                "X-Apay-Sign-Version": "1",
            },
        )
        response.raise_for_status()
        data = orjson.loads(response.content)

        if data.get("code") != 0:
            raise PaymentGatewayError(f"Antilopay API error: {data.get('message') or data}")

        payment_url = data.get("payment_url")
        if not payment_url:
            raise PaymentGatewayError("Antilopay response missing 'payment_url'")
        payment_id = data.get("payment_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-apay-callback")
        if not signature:
            raise PaymentGatewayError("Antilopay webhook missing X-Apay-Callback header")
        try:
            self._public_key().verify(
                base64.b64decode(signature), request.body, padding.PKCS1v15(), hashes.SHA256()
            )
        except InvalidSignature as error:
            raise PaymentGatewayError("Invalid Antilopay webhook signature") from error

        try:
            data = orjson.loads(request.body)
        except orjson.JSONDecodeError as error:
            raise PaymentGatewayError("Malformed Antilopay webhook") from error

        if data.get("type") != "payment":
            return None

        order_ref = data.get("order_id")
        if not order_ref:
            raise PaymentGatewayError("Antilopay webhook missing 'order_id'")

        if data.get("status") != "SUCCESS":
            return None
        return WebhookResult(reference=str(order_ref), status=PaymentOrderStatus.PAID)
