import hashlib
import base64
import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError, URL
from loguru import logger
from hmac import compare_digest

from src.core.config import AppConfig
from src.core.enums import TransactionStatus, Currency
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    CryptomusGatewaySettingsDto,
)
from .base import BasePaymentGateway


class CryptomusGateway(BasePaymentGateway):
    _client: AsyncClient

    CURRENCY = Currency.USD
    API_BASE: Final[str] = "https://api.cryptomus.com/v1/payment"

    NETWORKS = ["91.227.144.54"]

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.gateway.settings, CryptomusGatewaySettingsDto):
            raise TypeError("YoomoneyGateway requires CryptomusGatewaySettingsDto")

        self._client = self._make_client(base_url=self.API_BASE, headers={
            "merchant": self.gateway.settings.merchant_id,
            "Content-Type": "application/json",
        })

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        payload = await self._create_payment_payload(str(amount), str(uuid.uuid4()))

        try:
            response = await self._client.post("",
                                               json=payload,
                                               headers={"sign": self.generate_signature(orjson.dumps(payload))})
            response.raise_for_status()
            result = orjson.loads(response.content).get("result", {})
            return self._get_payment_data(result.get("url"), result.get("order_id"))

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
        logger.critical(request.headers)

        try:
            webhook_data = orjson.loads(await request.body())
            logger.debug(f"Webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError

            if not self.verify_notification(request, webhook_data):
                raise PermissionError("Webhook verification failed")

            status_str = webhook_data.get("status")
            payment_id_str = webhook_data.get("order_id")

            if not payment_id_str:
                raise ValueError("Required field 'id' is missing")

            try:
                payment_id = UUID(payment_id_str)
            except ValueError:
                raise ValueError("Invalid UUID format for payment ID")

            match status_str:
                case "paid" | "paid_over":
                    transaction_status = TransactionStatus.COMPLETED
                case "cancel":
                    transaction_status = TransactionStatus.CANCELED
                case _:
                    logger.info(f"Ignoring webhook status: {status_str}")
                    raise ValueError("Field 'status' not support")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def _create_payment_payload(self, amount: str, order_id: str) -> dict[str, Any]:
        return {
            "amount": amount,
            "currency": self.CURRENCY,
            "order_id": order_id,
            "url_return": self._get_bot_redirect_url(),
            "url_success": self._get_bot_redirect_url(),
            "url_callback": self.config.get_webhook(self.gateway.type),
            "lifetime": 1800,
            "is_payment_multiple": False,
        }

    def _get_payment_data(self, payment_url: URL, payment_id: str) -> PaymentResult:
        if not payment_url:
            raise KeyError("Invalid response from Yoomoney API: missing 'url'")

        return PaymentResult(id=UUID(payment_id), url=str(payment_url))

    def verify_notification(self, request: Request, data: dict) -> bool:
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For")
        )
        if not self._is_ip_trusted(client_ip):
            logger.warning(f"Webhook received from untrusted IP: '{client_ip}'")
            raise PermissionError("IP address is not trusted")

        sign = data.pop("sign", None)
        if not sign:
            raise ValueError("Missing signature")

        json_data = orjson.dumps(data)
        hash_value = self.generate_signature(json_data)

        if not compare_digest(hash_value, sign):
            logger.warning(f"Invalid signature.")
            return False

        return True

    def generate_signature(self, data: bytes) -> str:
        base64_encoded = base64.b64encode(data).decode()
        raw_string = f"{base64_encoded}{self.gateway.settings.api_key}"
        return hashlib.md5(raw_string.encode()).hexdigest()
