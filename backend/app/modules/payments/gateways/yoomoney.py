import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Final, Optional
from urllib.parse import parse_qs, quote

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
    http_client,
)

_API_BASE: Final[str] = "https://yoomoney.ru"
_TEST_NOTIFICATION: Final[str] = "test-notification"


class YooMoneyGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        payload = {
            "receiver": self._require("wallet_id"),
            "quickpay-form": "button",
            "paymentType": "AC",
            "sum": f"{order.final_price:.2f}",
            "label": order.idempotency_key,
            "successURL": self._return_url,
        }
        response = await http_client.post(
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

        # 'amount' is YooMoney's standard http-notification field for what the
        # sender actually paid (as opposed to 'withdraw_amount', net of fees).
        try:
            amount = Decimal(str(data.get("amount", "")))
        except InvalidOperation:
            amount = None

        return WebhookResult(
            reference=label,
            status=PaymentOrderStatus.PAID,
            provider_payment_id=data.get("operation_id"),
            amount=amount,
        )

    def _signature_valid(self, data: dict[str, str]) -> bool:
        received_sign = data.get("sign", "")
        if not received_sign:
            return False
        sign_str = "&".join(
            f"{key}={quote(value, safe='')}" for key, value in sorted(data.items()) if key != "sign"
        )
        secret = self._require("secret_key")
        computed_sign = hmac.new(
            secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_sign, received_sign)
