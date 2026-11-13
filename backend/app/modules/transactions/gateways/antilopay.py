import base64
import binascii
from typing import Any, Final, Optional

import orjson
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.gateways import AntilopaySettings
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    compact_json,
    load_rsa_public_key,
    parse_json,
    rsa_verify,
    to_decimal,
)

# v2 exists only for project/balance; every payment method is v1.
_API_BASE: Final[str] = "https://lk.antilopay.com/api/v1"
_CREATE_TIMEOUT_S: Final[float] = 20.0
_PAID_STATUS: Final[str] = "SUCCESS"
_PAYMENT_TYPE: Final[str] = "payment"
_OK_CODE: Final[int] = 0
_NOT_FOUND_CODE: Final[int] = 8


# Docs: https://doc.antilopay.com/AntilopayAPI.pdf
class AntilopayGateway(PaymentGateway[AntilopaySettings]):
    settings_model = AntilopaySettings
    currency = Currency.RUB

    @classmethod
    def requires_customer_email(cls, settings: dict[str, str]) -> bool:
        return True

    def _private_key(self) -> RSAPrivateKey:
        try:
            der = base64.b64decode(self.settings.private_key.get_secret_value().strip())
            key = serialization.load_der_private_key(der, password=None)
        except (ValueError, binascii.Error) as error:
            raise PaymentGatewayError("Malformed Antilopay private key") from error
        if not isinstance(key, RSAPrivateKey):
            raise PaymentGatewayError("Antilopay private key is not an RSA key")
        return key

    def _signed_headers(self, body: bytes) -> dict[str, str]:
        signature = self._private_key().sign(body, padding.PKCS1v15(), hashes.SHA256())
        return {
            "Content-Type": "application/json",
            "X-Apay-Secret-Id": self.settings.secret_id,
            "X-Apay-Sign": base64.b64encode(signature).decode("ascii"),
            "X-Apay-Sign-Version": "1",
        }

    async def _post(self, path: str, payload: dict[str, Any], *, timeout: float) -> Any:
        body = compact_json(payload)
        response = await self._http.post(
            f"{_API_BASE}/{path}",
            content=body,
            headers=self._signed_headers(body),
            timeout=timeout,
        )
        response.raise_for_status()
        return orjson.loads(response.content)

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        data = await self._post(
            "payment/create",
            {
                "project_identificator": self.settings.project_id,
                "amount": amount_to_float(order.final_price),
                "order_id": order.idempotency_key,
                "currency": order.currency.value.lower(),
                "product_name": f"Order #{order.id}",
                "product_type": "services",
                "description": f"Order #{order.id}",
                "customer": {"email": order.customer_email},
                "success_url": self._return_url,
                "fail_url": self._return_url,
            },
            timeout=_CREATE_TIMEOUT_S,
        )
        if data.get("code") != _OK_CODE:
            raise PaymentGatewayError(f"Antilopay API error: {data.get('error') or data}")

        payment_url = data.get("payment_url")
        if not payment_url:
            raise PaymentGatewayError("Antilopay response missing 'payment_url'")
        payment_id = data.get("payment_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("x-apay-callback", "")
        public_key = load_rsa_public_key(self.settings.public_key.get_secret_value())
        if not signature or not rsa_verify(public_key, signature, request.body, hashes.SHA256()):
            raise PaymentGatewayError("Invalid Antilopay webhook signature")

        data = parse_json(request.body, "Antilopay")
        if data.get("type") != _PAYMENT_TYPE:
            return None
        order_ref = data.get("order_id")
        if not order_ref:
            raise PaymentGatewayError("Antilopay webhook missing 'order_id'")
        payment_id = data.get("payment_id")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=data.get("status") == _PAID_STATUS,
            provider_payment_id=str(payment_id) if payment_id else None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        data = await self._post(
            "payment/check",
            {
                "project_identificator": self.settings.project_id,
                "order_id": order.idempotency_key,
            },
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        code = data.get("code")
        if code == _NOT_FOUND_CODE:
            return NOT_PAID
        if code != _OK_CODE:
            raise PaymentGatewayError(f"Antilopay payment/check error: {data.get('error') or data}")
        payment_id = data.get("payment_id")
        # `amount` is net of the fee; the docs require checking original_amount.
        return ProviderPayment(
            paid=data.get("status") == _PAID_STATUS,
            amount=to_decimal(data.get("original_amount")),
            currency=data.get("currency"),
            reference=str(data.get("order_id") or ""),
            provider_payment_id=str(payment_id) if payment_id else None,
        )
