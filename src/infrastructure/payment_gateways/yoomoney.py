import hashlib
import uuid
from decimal import Decimal
from typing import Any, Final
from urllib.parse import parse_qs
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.application.dto import (
    PaymentGatewayDto,
    PaymentResultDto,
)
from src.application.dto.payment_gateway import YooMoneyGatewaySettingsDto
from src.core.config import AppConfig
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


# https://yoomoney.ru/docs/
class YoomoneyGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://yoomoney.ru"
    PAY_FORM: Final[str] = "button"
    PAY_TYPE: Final[str] = "AC"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, YooMoneyGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {YooMoneyGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )

        self._client = self._make_client(base_url=self.API_BASE)

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        payment_id = uuid.uuid4()
        payload = await self._create_payment_payload(str(amount), str(payment_id))
        logger.debug(f"Creating payment payload: {payload}")

        try:
            response = await self._client.post(
                "quickpay/confirm.xml",
                json=payload,
                follow_redirects=True,
            )
            response.raise_for_status()
            return PaymentResultDto(id=payment_id, url=str(response.url))

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
        logger.debug("Received YooMoney webhook request")
        webhook_data = await self._get_webhook_data(request)
        operation_id = webhook_data.get("operation_id")

        if operation_id == "test-notification":
            raise ValueError("Test webhook cannot be processed")

        if not self._verify_webhook(webhook_data):
            raise ValueError("YooMoney verification failed")

        payment_id_str = webhook_data.get("label")

        if not payment_id_str:
            raise ValueError("Required field 'label' is missing")

        payment_id = UUID(payment_id_str)
        transaction_status = TransactionStatus.COMPLETED

        return payment_id, transaction_status

    async def _get_webhook_data(self, request: Request) -> dict:
        try:
            body_bytes = await request.body()
            body_str = body_bytes.decode("utf-8")
            parsed = parse_qs(body_str)
            data = {k: v[0] for k, v in parsed.items()}
            logger.debug(f"Webhook data: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            raise ValueError("Invalid webhook payload") from e

    async def _create_payment_payload(
        self,
        amount: str,
        label: str,
    ) -> dict[str, Any]:
        return {
            "receiver": self.data.settings.wallet_id,  # type: ignore[union-attr]
            "quickpay-form": self.PAY_FORM,
            "paymentType": self.PAY_TYPE,
            "sum": amount,
            "label": label,
            "successURL": await self._get_bot_redirect_url(),
        }

    def _verify_webhook(self, data: dict) -> bool:
        params = [
            data.get("notification_type", ""),
            data.get("operation_id", ""),
            data.get("amount", ""),
            data.get("currency", ""),
            data.get("datetime", ""),
            data.get("sender", ""),
            data.get("codepro", ""),
            self.data.settings.secret_key.get_secret_value(),  # type: ignore[union-attr]
            data.get("label", ""),
        ]

        sign_str = "&".join(params)
        computed_hash = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

        is_valid: bool = computed_hash == data.get("sha1_hash", "")
        if not is_valid:
            logger.warning(
                f"Invalid signature. Expected {computed_hash}, received {data.get('sha1_hash')}"
            )

        return is_valid
