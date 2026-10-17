from typing import Final, Optional
from urllib.parse import quote

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    hmac_hex,
    parse_form,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://yoomoney.ru"
_TEST_NOTIFICATION: Final[str] = "test-notification"
_PAID_STATUS: Final[str] = "success"
_INCOMING: Final[str] = "in"


# Docs: https://yoomoney.ru/docs/wallet
class YooMoneyGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "receiver": self._require("wallet_id"),
            "quickpay-form": "button",
            "paymentType": "AC",
            "sum": f"{order.final_price:.2f}",
            "label": order.idempotency_key,
            "successURL": self._return_url,
        }
        response = await self._http.post(
            f"{_API_BASE}/quickpay/confirm.xml", data=payload, follow_redirects=True
        )
        response.raise_for_status()
        return PaymentIntent(confirmation_url=str(response.url), provider_payment_id=None)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = parse_form(request.body, "YooMoney")
        if data.get("operation_id") == _TEST_NOTIFICATION:
            return None
        if not self._signature_valid(data):
            raise PaymentGatewayError("Invalid YooMoney webhook signature")

        label = data.get("label")
        if not label:
            raise PaymentGatewayError("YooMoney webhook missing 'label'")
        # withdraw_amount is what the sender paid; amount is net of the fee.
        unaccepted = data.get("unaccepted") == "true"
        codepro = data.get("codepro") == "true"
        return WebhookSignal(
            reference=label,
            claims_paid=not (unaccepted or codepro),
            provider_payment_id=data.get("operation_id") or None,
            amount=to_decimal(data.get("withdraw_amount")),
        )

    def _signature_valid(self, data: dict[str, str]) -> bool:
        received_sign = data.get("sign", "")
        if not received_sign:
            return False
        message = "&".join(
            f"{key}={quote(value, safe='')}" for key, value in sorted(data.items()) if key != "sign"
        )
        expected = hmac_hex(self._require("secret_key"), message.encode("utf-8"))
        return safe_equals(expected, received_sign)

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if signal.amount is None:
            return NOT_PAID
        token = self._optional("access_token")
        if token is None:
            return ProviderPayment(
                paid=True,
                amount=signal.amount,
                reference=signal.reference,
                provider_payment_id=signal.provider_payment_id,
            )
        if not signal.provider_payment_id:
            return NOT_PAID

        response = await self._http.post(
            f"{_API_BASE}/api/operation-details",
            data={"operation_id": signal.provider_payment_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        details = orjson.loads(response.content)
        if details.get("error"):
            raise PaymentGatewayError(f"YooMoney operation-details error: {details['error']}")
        return ProviderPayment(
            paid=details.get("status") == _PAID_STATUS and details.get("direction") == _INCOMING,
            amount=signal.amount,
            reference=str(details.get("label") or ""),
            provider_payment_id=str(details.get("operation_id") or signal.provider_payment_id),
        )
