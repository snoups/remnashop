from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from ipaddress import ip_address, ip_network
from typing import Final, Iterable, Optional

import httpx

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto

_HTTP_TIMEOUT_S: Final[float] = 20.0
http_client: Final[httpx.AsyncClient] = httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S)


@dataclass(frozen=True, kw_only=True)
class WebhookRequest:
    body: bytes
    headers: dict[str, str]
    query: dict[str, str]
    client_ip: Optional[str]


@dataclass(frozen=True, kw_only=True)
class PaymentIntent:
    confirmation_url: Optional[str]
    provider_payment_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class WebhookResult:
    reference: str
    status: PaymentOrderStatus
    provider_payment_id: Optional[str] = None
    # Amount the provider says was actually paid, parsed from the webhook body
    # itself -- None when a gateway's webhook carries no such field (checked
    # against order.final_price by the default verify_payment below).
    amount: Optional[Decimal] = None


def amount_to_float(value: Decimal) -> float:
    """Round to 2 places on the Decimal before the float conversion, so
    gateways needing a JSON number agree with the ones formatting a string."""
    return float(f"{value:.2f}")


def ip_in_networks(ip: str, networks: Iterable[str]) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    for net in networks:
        try:
            if addr in ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False


class PaymentGateway(ABC):
    currency: Currency
    trusted_networks: tuple[str, ...] = ()

    def __init__(self, *, settings: dict[str, str], webhook_url: str, return_url: str) -> None:
        self._settings = settings
        self._webhook_url = webhook_url
        self._return_url = return_url

    def _require(self, key: str) -> str:
        value = self._settings.get(key)
        if not value:
            raise PaymentGatewayError(f"{type(self).__name__}: missing required setting '{key}'")
        return value

    def _optional(self, key: str) -> Optional[str]:
        return self._settings.get(key) or None

    @abstractmethod
    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent: ...

    @abstractmethod
    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        """Verify signature/IP and extract (reference, status). Return None
        for webhooks carrying no state change (test pings, confirm_check).
        Raise PaymentGatewayError on a verification failure."""

    async def verify_payment(self, order: PaymentOrderDto, result: WebhookResult) -> bool:
        if result.amount is None:
            return True
        return result.amount >= order.final_price

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return ""
