from abc import ABC, abstractmethod
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Iterable, Optional

from app.core.enums import Currency, PaymentOrderStatus
from app.modules.payments.dto import PaymentOrderDto


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

    @abstractmethod
    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent: ...

    @abstractmethod
    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        """Verify signature/IP and extract (reference, status). Return None
        for webhooks carrying no state change (test pings, confirm_check).
        Raise PaymentGatewayError on a verification failure."""

    async def verify_payment(self, order: PaymentOrderDto) -> bool:
        return True

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return ""
