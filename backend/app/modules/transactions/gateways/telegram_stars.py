from decimal import ROUND_CEILING
from typing import Final, Optional

import httpx
import orjson

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.core.telegram_api import bot_method_url
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookRequest,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import PROVIDER_API_TIMEOUT_S

BOT_TOKEN_SETTING: Final[str] = "bot_token"
BOT_PROXY_SETTING: Final[str] = "bot_proxy"
# Telegram caps invoice titles at 32 characters
_TITLE_MAX: Final[int] = 32
_NO_WEBHOOK: Final[str] = "Telegram Stars has no HTTP webhook"


def stars_amount(order: TransactionDto) -> int:
    return int(order.final_price.to_integral_value(rounding=ROUND_CEILING))


# Docs: https://core.telegram.org/bots/payments-stars
class TelegramStarsGateway(PaymentGateway):
    currency = Currency.XTR

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=PROVIDER_API_TIMEOUT_S, proxy=self._optional(BOT_PROXY_SETTING)
        )

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        name = order.plan_snapshot.name
        body = {
            "title": name[:_TITLE_MAX],
            "description": f"{name}, {order.duration_days}d",
            "payload": order.idempotency_key,
            "currency": Currency.XTR.value,
            "prices": [{"label": Currency.XTR.value, "amount": stars_amount(order)}],
        }
        async with self._client() as client:
            response = await client.post(
                bot_method_url(self._require(BOT_TOKEN_SETTING), "createInvoiceLink"), json=body
            )
        payload = orjson.loads(response.content)
        if not payload.get("ok"):
            raise PaymentGatewayError(f"createInvoiceLink refused: {payload.get('description')}")
        return PaymentIntent(confirmation_url=str(payload["result"]))

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # paid inside Telegram: successful_payment reaches the bot, not this endpoint
        raise PaymentGatewayError(_NO_WEBHOOK)

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        raise PaymentGatewayError(_NO_WEBHOOK)
