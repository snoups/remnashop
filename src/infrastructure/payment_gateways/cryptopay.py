import hashlib
import hmac
import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.application.dto import PaymentGatewayDto, PaymentResultDto
from src.application.dto.payment_gateway import CryptoPayGatewaySettingsDto
from src.core.config import AppConfig
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


# https://help.send.tg/articles/10279948-crypto-pay-api/
class CryptoPayGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://pay.crypt.bot/api"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, CryptoPayGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {CryptoPayGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={"Crypto-Pay-API-Token": self.data.settings.api_key.get_secret_value()},  # type: ignore[union-attr]
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        payload = await self._create_payment_payload(str(amount), details)
        logger.debug(f"Creating payment payload: {payload}")

        try:
            response = await self._client.post("createInvoice", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)

            if not data.get("ok"):
                error = data.get("error", {})
                raise ValueError(f"CryptoPay API error: {error}")

            return self._get_payment_data(data.get("result", {}))

        except HTTPStatusError as e:
            logger.error(
                f"HTTP error creating payment. "
                f"Status: '{e.response.status_code}', Body: {e.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as e:
            logger.error(f"Failed to parse response. Error: {e}")
            raise
        except Exception as e:
            logger.exception(f"An unexpected error occurred while creating payment: {e}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        logger.debug(f"Received {self.__class__.__name__} webhook request")

        body = await request.body()
        webhook_data = orjson.loads(body)

        if not self._verify_webhook(request, body):
            raise PermissionError("Webhook verification failed")

        if webhook_data.get("update_type") != "invoice_paid":
            raise ValueError(f"Unsupported update_type: {webhook_data.get('update_type')}")

        invoice: dict = webhook_data.get("payload", {})
        payload_str = invoice.get("payload")

        if not payload_str:
            raise ValueError("Required field 'payload' (order_id) is missing in invoice")

        status = invoice.get("status")
        payment_id = UUID(payload_str)

        match status:
            case "paid":
                transaction_status = TransactionStatus.COMPLETED
            case "expired":
                transaction_status = TransactionStatus.CANCELED
            case _:
                raise ValueError(f"Unsupported invoice status: {status}")

        return payment_id, transaction_status

    async def _create_payment_payload(self, amount: str, details: str) -> dict[str, Any]:
        order_id = str(uuid.uuid4())
        return {
            "currency_type": "fiat",
            "fiat": self.data.currency.value,
            "amount": amount,
            "description": details,
            "payload": order_id,
            "paid_btn_name": "openBot",
            "paid_btn_url": await self._get_bot_redirect_url(),
            "expires_in": 1800,
        }

    def _get_payment_data(self, data: dict[str, Any]) -> PaymentResultDto:
        payload_str = data.get("payload")
        if not payload_str:
            raise KeyError("Invalid response from CryptoPay API: missing 'payload'")

        payment_url = data.get("bot_invoice_url")
        if not payment_url:
            raise KeyError("Invalid response from CryptoPay API: missing 'bot_invoice_url'")

        return PaymentResultDto(id=UUID(payload_str), url=str(payment_url))

    def _verify_webhook(self, request: Request, raw_body: bytes) -> bool:
        signature = request.headers.get("crypto-pay-api-signature")
        if not signature:
            logger.warning("Webhook is missing 'crypto-pay-api-signature' header")
            return False

        api_token = self.data.settings.api_key.get_secret_value()  # type: ignore[union-attr]
        secret = hashlib.sha256(api_token.encode()).digest()
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("Invalid CryptoPay webhook signature")
            return False

        return True
