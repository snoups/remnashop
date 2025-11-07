import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.enums import TransactionStatus, YookassaVatCode
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    YookassaGatewaySettingsDto,
)

from .base import BasePaymentGateway


class YookassaGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://api.yookassa.ru/v3/payments"
    PAYMENT_SUBJECT: Final[str] = "service"
    PAYMENT_MODE: Final[str] = "full_payment"

    VAT_CODE: Final[YookassaVatCode] = YookassaVatCode.VAT_CODE_01
    CUSTOMER: Final[str] = "test@remnashop.com"

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

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, YookassaGatewaySettingsDto):
            raise TypeError("YookassaGateway requires YookassaGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            auth=(
                self.gateway.settings.shop_id,
                self.gateway.settings.api_key.get_secret_value(),  # type: ignore [arg-type, union-attr]
            ),
            headers={"Content-Type": "application/json"},
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        headers = {"Idempotence-Key": str(uuid.uuid4())}
        payload = await self._create_payment_payload(str(amount), details)

        try:
            content = orjson.dumps(payload)
            response = await self._client.post("", headers=headers, content=content)
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
        client_ip = request.headers.get("X-Forwarded-For", "")
        logger.critical(request.headers)

        if not self._is_ip_trusted(client_ip):
            logger.warning(f"Webhook received from untrusted IP: '{client_ip}'")
            raise PermissionError("IP address is not trusted")

        try:
            webhook_data = orjson.loads(await request.body())
            logger.debug(f"Webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError

            payment_object: dict = webhook_data.get("object", {})
            payment_id_str = payment_object.get("id")
            status_str = payment_object.get("status")

            if not payment_id_str or not status_str:
                raise ValueError("Required fields 'id' or 'status' are missing")

            try:
                payment_id = UUID(payment_id_str)
            except ValueError:
                raise ValueError("Invalid UUID format for payment ID")

            match status_str:
                case "succeeded":
                    transaction_status = TransactionStatus.COMPLETED
                case "canceled":
                    transaction_status = TransactionStatus.CANCELED
                case _:
                    logger.info(f"Ignoring webhook status: {status_str}")
                    raise ValueError("Field 'status' not support")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def _create_payment_payload(self, amount: str, details: str) -> dict[str, Any]:
        return {
            "amount": {"value": amount, "currency": self.gateway.currency},
            "confirmation": {"type": "redirect", "return_url": await self._get_bot_redirect_url()},
            "capture": True,
            "description": details,
            "receipt": {
                "customer": {"email": self.gateway.settings.customer or self.CUSTOMER},  # type: ignore[union-attr]
                "items": [
                    {
                        "description": details,
                        "quantity": "1.00",
                        "amount": {"value": amount, "currency": self.gateway.currency},
                        "vat_code": self.gateway.settings.vat_code or self.VAT_CODE,  # type: ignore[union-attr]
                        "payment_subject": self.PAYMENT_SUBJECT,
                        "payment_mode": self.PAYMENT_MODE,
                    }
                ],
            },
        }

    def _get_payment_data(self, data: dict[str, Any]) -> PaymentResult:
        payment_id_str = data.get("id")

        if not payment_id_str:
            raise KeyError("Invalid response from Yookassa API: missing 'id'")

        confirmation: dict = data.get("confirmation", {})
        payment_url = confirmation.get("confirmation_url")

        if not payment_url:
            raise KeyError("Invalid response from Yookassa API: missing 'confirmation_url'")

        return PaymentResult(id=UUID(payment_id_str), url=str(payment_url))
