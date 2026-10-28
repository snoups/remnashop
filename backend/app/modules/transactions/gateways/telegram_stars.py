from decimal import ROUND_CEILING
from typing import Final, Optional, TypeVar

from aiogram.methods import CreateInvoiceLink, RefundStarPayment, TelegramMethod
from aiogram.types import LabeledPrice
from pydantic import SecretStr

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.core.telegram_api import BOT_API_ERRORS, bot_api_error_text, bot_client
from app.modules.gateways import TelegramStarsSettings
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import PROVIDER_API_TIMEOUT_S

BOT_TOKEN_SETTING: Final[str] = "bot_token"
BOT_PROXY_SETTING: Final[str] = "bot_proxy"
T = TypeVar("T")
# Telegram caps invoice titles at 32 characters
_TITLE_MAX: Final[int] = 32
_NO_WEBHOOK: Final[str] = "Telegram Stars has no HTTP webhook"
_ALREADY_REFUNDED: Final[str] = "CHARGE_ALREADY_REFUNDED"


class StarsRuntimeSettings(TelegramStarsSettings):
    # not dashboard fields: the bot's token and proxy, added by with_bot_settings()
    bot_token: SecretStr
    bot_proxy: Optional[str] = None


def with_bot_settings(settings: dict[str, str], token: str, proxy: Optional[str]) -> dict[str, str]:
    return {**settings, BOT_TOKEN_SETTING: token, BOT_PROXY_SETTING: proxy or ""}


def stars_amount(order: TransactionDto) -> int:
    return int(order.final_price.to_integral_value(rounding=ROUND_CEILING))


# Docs: https://core.telegram.org/bots/payments-stars
class TelegramStarsGateway(PaymentGateway[StarsRuntimeSettings]):
    settings_model = StarsRuntimeSettings
    currency = Currency.XTR

    async def _call(self, method: TelegramMethod[T]) -> T:
        try:
            async with bot_client(
                self.settings.bot_token.get_secret_value(),
                self.settings.bot_proxy,
                timeout=PROVIDER_API_TIMEOUT_S,
            ) as bot:
                return await bot(method)
        except BOT_API_ERRORS as error:
            # from None: the chained network error can carry the request URL, token included
            raise PaymentGatewayError(
                f"{type(method).__name__} refused: {bot_api_error_text(error)}"
            ) from None

    async def refund(self, charge_id: str, telegram_id: int) -> None:
        try:
            await self._call(
                RefundStarPayment(user_id=telegram_id, telegram_payment_charge_id=charge_id)
            )
        except PaymentGatewayError as error:
            # a retry after a lost answer or a failed DB write must still complete
            if _ALREADY_REFUNDED not in str(error):
                raise

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        name = order.plan_snapshot.name
        link = await self._call(
            CreateInvoiceLink(
                title=name[:_TITLE_MAX],
                description=f"{name}, {order.duration_days}d",
                payload=order.idempotency_key,
                currency=Currency.XTR.value,
                prices=[LabeledPrice(label=Currency.XTR.value, amount=stars_amount(order))],
            )
        )
        return PaymentIntent(confirmation_url=link)

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        # paid inside Telegram: successful_payment reaches the bot, not this endpoint
        raise PaymentGatewayError(_NO_WEBHOOK)

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        raise PaymentGatewayError(_NO_WEBHOOK)
