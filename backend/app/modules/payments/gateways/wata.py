from base64 import b64decode
from typing import Final, Optional

import orjson
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
    amount_to_float,
    http_client,
)

_API_BASE: Final[str] = "https://api.wata.pro/api/h2h"


class WataGateway(PaymentGateway):
    currency = Currency.USD

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "type": "OneTime",
            "amount": amount_to_float(order.final_price),
            "currency": order.currency.value,
            "description": f"Order #{order.id}",
            "orderId": order.idempotency_key,
            "successRedirectUrl": self._return_url,
            "failRedirectUrl": self._return_url,
        }
        response = await http_client.post(
            f"{_API_BASE}/links",
            json=payload,
            headers={"Authorization": f"Bearer {self._require('api_key')}"},
        )
        response.raise_for_status()
        payment_url = orjson.loads(response.content).get("url")
        if not payment_url:
            raise PaymentGatewayError("WATA response missing 'url'")
        return PaymentIntent(confirmation_url=str(payment_url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        signature = request.headers.get("x-signature")
        if not signature:
            raise PaymentGatewayError("WATA webhook missing X-Signature header")

        # fetches WATA's public key on every webhook; add a TTL cache
        # if webhook volume ever makes the extra GET matter.
        public_key = await self._fetch_public_key()
        try:
            public_key.verify(
                b64decode(signature), request.body, padding.PKCS1v15(), hashes.SHA512()
            )
        except InvalidSignature as error:
            raise PaymentGatewayError("Invalid WATA webhook signature") from error

        data = orjson.loads(request.body)
        order_ref = data.get("orderId")
        if not order_ref:
            raise PaymentGatewayError("WATA webhook missing 'orderId'")

        if data.get("transactionStatus") != "Paid":
            return None
        return WebhookResult(reference=str(order_ref), status=PaymentOrderStatus.PAID)

    async def _fetch_public_key(self) -> RSAPublicKey:
        response = await http_client.get(
            f"{_API_BASE}/public-key",
            headers={"Authorization": f"Bearer {self._require('api_key')}"},
        )
        response.raise_for_status()
        pem = orjson.loads(response.content)["value"].encode()
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, RSAPublicKey):
            raise PaymentGatewayError("WATA public key is not an RSA key")
        return key
