from abc import ABC, abstractmethod
from decimal import Decimal
from ipaddress import ip_address, ip_network
from typing import Optional, Protocol
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, Timeout
from loguru import logger
from starlette.datastructures import Headers

from src.core.config.app import AppConfig
from src.core.constants import T_ME
from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import PaymentGatewayDto, PaymentResult


class PaymentGatewayFactory(Protocol):
    def __call__(self, gateway: "PaymentGatewayDto") -> "BasePaymentGateway": ...


class BasePaymentGateway(ABC):
    data: PaymentGatewayDto
    bot: Bot

    _bot_username: Optional[str]

    NETWORKS: list[str] = []

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        self.data = gateway
        self.bot = bot
        self.config = config
        self._bot_username: Optional[str] = None

        logger.debug(f"{self.__class__.__name__} Initialized")

    @abstractmethod
    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult: ...

    @abstractmethod
    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]: ...

    async def _get_bot_redirect_url(self) -> str:
        if self._bot_username is None:
            self._bot_username = (await self.bot.get_me()).username
        return f"{T_ME}{self._bot_username}"

    async def _get_webhook_data(self, request: Request) -> dict:
        try:
            data = orjson.loads(await request.body())
            logger.debug(f"Webhook data: {data}")

            if not isinstance(data, dict):
                raise ValueError("Payload is not a dictionary")

            return data
        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

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

    def _get_ip(self, headers: Headers) -> str:
        ip = (
            headers.get("CF-Connecting-IP")
            or headers.get("X-Real-IP")
            or headers.get("X-Forwarded-For")
        )

        if not ip:
            raise PermissionError("Client IP not found in request headers")

        return ip
