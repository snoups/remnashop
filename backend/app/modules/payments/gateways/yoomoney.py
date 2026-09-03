import hashlib
import hmac
from typing import Final, Optional
from urllib.parse import parse_qs, quote

import httpx

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
)

_API_BASE: Final[str] = "https://yoomoney.ru"
_TIMEOUT_S: Final[float] = 15.0
_TEST_NOTIFICATION: Final[str] = "test-notification"

_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_TIMEOUT_S)


class YooMoneyGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "receiver": self._settings["wallet_id"],
            "quickpay-form": "button",
            "paymentType": "AC",
            "sum": f"{order.final_price:.2f}",
            "label": order.idempotency_key,
            "successURL": self._return_url,
        }
        response = await _client.post(
            f"{_API_BASE}/quickpay/confirm.xml", data=payload, follow_redirects=True
        )
        response.raise_for_status()
        return PaymentIntent(confirmation_url=str(response.url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            parsed = parse_qs(request.body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError as error:
            raise PaymentGatewayError("Malformed YooMoney webhook") from error
        data = {key: values[0] for key, values in parsed.items()}

        if data.get("operation_id") == _TEST_NOTIFICATION:
            return None

        if not self._signature_valid(data):
            raise PaymentGatewayError("Invalid YooMoney webhook signature")

        label = data.get("label")
        if not label:
            raise PaymentGatewayError("YooMoney webhook missing 'label'")

        return WebhookResult(
            reference=label,
            status=PaymentOrderStatus.PAID,
            provider_payment_id=data.get("operation_id"),
        )

    def _signature_valid(self, data: dict[str, str]) -> bool:
        received_sign = data.get("sign", "")
        if not received_sign:
            return False
        sign_str = "&".join(
            f"{key}={quote(value, safe='')}" for key, value in sorted(data.items()) if key != "sign"
        )
        secret = self._settings["secret_key"]
        computed_sign = hmac.new(
            secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_sign, received_sign)
