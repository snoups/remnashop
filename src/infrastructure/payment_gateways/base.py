from abc import ABC, abstractmethod
from decimal import Decimal
from ipaddress import ip_address, ip_network
from typing import Optional, Protocol
from uuid import UUID

from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, Timeout
from loguru import logger

from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import PaymentGatewayDto, PaymentResult


class PaymentGatewayFactory(Protocol):
    def __call__(self, gateway: "PaymentGatewayDto") -> "BasePaymentGateway": ...


class BasePaymentGateway(ABC):
    gateway: PaymentGatewayDto
    bot: Bot

    _bot_username: Optional[str]

    NETWORKS: list[str] = []

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
    ) -> None:
        self.gateway = gateway
        self.bot = bot
        self._bot_username: Optional[str] = None

        logger.debug(f"{self.__class__.__name__} Initialized")

    @abstractmethod
    async def handle_create_payment(
        self,
        amount: Decimal,
        details: str,
    ) -> PaymentResult: ...

    @abstractmethod
    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]: ...

    async def _get_bot_redirect_url(self) -> str:
        if self._bot_username is None:
            self._bot_username = (await self.bot.get_me()).username
        return f"https://t.me/{self._bot_username}"

    def _make_client(
        self,
        base_url: str,
        auth: Optional[tuple[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> AsyncClient:
        return AsyncClient(base_url=base_url, auth=auth, headers=headers, timeout=Timeout(timeout))

    def _is_test_payment(self, payment_id: str) -> bool:
        return payment_id.startswith("test:")

    def _is_ip_in_network(self, ip: str, network: str) -> bool:
        try:
            return ip_address(ip) in ip_network(network, strict=False)
        except Exception as exception:
            logger.error(f"Failed to check IP '{ip}' in network '{network}': {exception}")
            return False

    def _is_ip_trusted(self, ip: str) -> bool:
        return any(self._is_ip_in_network(ip, net) for net in self.NETWORKS)
