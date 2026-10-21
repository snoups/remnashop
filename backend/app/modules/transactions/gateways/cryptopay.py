import hashlib
import hmac
from typing import Final, Optional

import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.gateways import CryptoPaySettings
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
    link_lifetime,
    parse_json,
    safe_equals,
    to_decimal,
)

_API_BASE: Final[str] = "https://pay.crypt.bot/api"
_MAX_EXPIRES_IN_S: Final[int] = 2678400
_PAID_STATUS: Final[str] = "paid"
_PAID_UPDATE: Final[str] = "invoice_paid"


# Docs: https://help.cr.bot/ru/articles/10279948-crypto-pay-api
class CryptoPayGateway(PaymentGateway[CryptoPaySettings]):
    settings_model = CryptoPaySettings
    currency = Currency.USD

    def _headers(self) -> dict[str, str]:
        return {"Crypto-Pay-API-Token": self.settings.api_key.get_secret_value()}

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        payload = {
            "currency_type": "fiat",
            "fiat": order.currency.value,
            "amount": f"{order.final_price:.2f}",
            "description": f"Order #{order.id}",
            "payload": order.idempotency_key,
            "paid_btn_name": "openBot",
            "paid_btn_url": self._return_url,
            "expires_in": link_lifetime(order, unit="seconds", maximum=_MAX_EXPIRES_IN_S),
        }
        response = await self._http.post(
            f"{_API_BASE}/createInvoice", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("ok"):
            raise PaymentGatewayError(f"CryptoPay API error: {data.get('error')}")

        result = data.get("result") or {}
        payment_url = result.get("bot_invoice_url")
        if not payment_url:
            raise PaymentGatewayError("CryptoPay response missing 'bot_invoice_url'")
        invoice_id = result.get("invoice_id")
        return PaymentIntent(
            confirmation_url=str(payment_url),
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        signature = request.headers.get("crypto-pay-api-signature", "")
        secret = hashlib.sha256(self.settings.api_key.get_secret_value().encode("utf-8")).digest()
        expected = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
        if not signature or not safe_equals(expected, signature):
            raise PaymentGatewayError("Invalid CryptoPay webhook signature")

        data = parse_json(request.body, "CryptoPay")
        if data.get("update_type") != _PAID_UPDATE:
            return None
        invoice = data.get("payload") or {}
        order_ref = invoice.get("payload")
        if not order_ref:
            raise PaymentGatewayError("CryptoPay invoice missing 'payload'")
        invoice_id = invoice.get("invoice_id")
        return WebhookSignal(
            reference=str(order_ref),
            claims_paid=invoice.get("status") == _PAID_STATUS,
            provider_payment_id=str(invoice_id) if invoice_id else None,
        )

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if not order.external_payment_id:
            return NOT_PAID
        response = await self._http.get(
            f"{_API_BASE}/getInvoices",
            params={"invoice_ids": order.external_payment_id},
            headers=self._headers(),
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not data.get("ok"):
            raise PaymentGatewayError(f"CryptoPay getInvoices error: {data.get('error')}")
        result = data.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        invoice = next(
            (
                item
                for item in items or []
                if str(item.get("invoice_id")) == order.external_payment_id
            ),
            None,
        )
        if invoice is None:
            return NOT_PAID
        is_fiat = invoice.get("currency_type") == "fiat"
        return ProviderPayment(
            paid=invoice.get("status") == _PAID_STATUS,
            amount=to_decimal(invoice.get("amount")),
            currency=invoice.get("fiat") if is_fiat else invoice.get("asset"),
            reference=str(invoice.get("payload") or ""),
            provider_payment_id=str(invoice.get("invoice_id")),
        )
