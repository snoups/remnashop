import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    YookassaGatewaySettingsDto,
)

from .base import BasePaymentGateway


class YookassaGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://api.yookassa.ru"
    PAYMENT_SUBJECT: Final[str] = "service"
    PAYMENT_MODE: Final[str] = "full_payment"

    NETWORKS = [
        "77.75.153.0/25",
        "77.75.156.11",
        "77.75.156.35",
        "77.75.154.128/25",
        "185.71.76.0/27",
        "185.71.77.0/27",
        "2a02:5180:0:1509::/64",
        "2a02:5180:0:2655::/64",
        "2a02:5180:0:1533::/64",
        "2a02:5180:0:2669::/64",
    ]

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, YookassaGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {YookassaGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )

        self._client = self._make_client(
            base_url=self.API_BASE,
            auth=(
                self.data.settings.shop_id,
                self.data.settings.api_key.get_secret_value(),  # type: ignore [arg-type, union-attr]
            ),
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        payload = await self._create_payment_payload(str(amount), details)
        headers = {"Idempotence-Key": str(uuid.uuid4())}

        try:
            response = await self._client.post("v3/payments", json=payload, headers=headers)
            response.raise_for_status()
            data = orjson.loads(response.content)
            return self._get_payment_data(data)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        logger.debug("Received YooKassa webhook request")

        if not self._verify_webhook(request):
            raise PermissionError("Webhook verification failed")

        webhook_data = await self._get_webhook_data(request)
        payment_object: dict = webhook_data.get("object", {})
        payment_id_str = payment_object.get("id")

        if not payment_id_str:
            raise ValueError("Required field 'id' is missing")

        status = payment_object.get("status")
        payment_id = UUID(payment_id_str)

        match status:
            case "succeeded":
                transaction_status = TransactionStatus.COMPLETED
            case "canceled":
                transaction_status = TransactionStatus.CANCELED
            case _:
                raise ValueError(f"Unsupported status: {status}")

        return payment_id, transaction_status

    async def _create_payment_payload(self, amount: str, details: str) -> dict[str, Any]:
        return {
            "amount": {"value": amount, "currency": self.data.currency},
            "confirmation": {"type": "redirect", "return_url": await self._get_bot_redirect_url()},
            "capture": True,
            "description": details,
            "receipt": {
                "customer": {"email": self.data.settings.customer},  # type: ignore[union-attr]
                "items": [
                    {
                        "description": details,
                        "quantity": "1.00",
                        "amount": {"value": amount, "currency": self.data.currency},
                        "vat_code": self.data.settings.vat_code,  # type: ignore[union-attr]
                        "payment_subject": self.PAYMENT_SUBJECT,
                        "payment_mode": self.PAYMENT_MODE,
                    }
                ],
            },
        }

    def _get_payment_data(self, data: dict[str, Any]) -> PaymentResult:
        payment_id_str = data.get("id")

        if not payment_id_str:
            raise KeyError("Invalid response from YooKassa API: missing 'id'")

        confirmation: dict = data.get("confirmation", {})
        payment_url = confirmation.get("confirmation_url")

        if not payment_url:
            raise KeyError("Invalid response from YooKassa API: missing 'confirmation_url'")

        return PaymentResult(id=UUID(payment_id_str), url=str(payment_url))

    def _verify_webhook(self, request: Request) -> bool:
        ip = self._get_ip(request.headers)

        if not self._is_ip_trusted(ip):
            logger.critical(f"Webhook received from untrusted IP: '{ip}'")
            return False

        return True
