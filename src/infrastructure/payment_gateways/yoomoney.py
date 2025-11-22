import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
import hashlib
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError, URL
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    YoomoneyGatewaySettingsDto,
)

from .base import BasePaymentGateway


class YoomoneyGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://yoomoney.ru/quickpay/confirm.xml?"
    PAY_FORM: Final[str] = "shop"
    PAY_TYPE: Final[str] = "SB"

    NETWORKS = [
        "77.75.153.0/25",
        "77.75.156.11",
        "77.75.156.35",
        "77.75.157.0/255"
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

        if not isinstance(self.gateway.settings, YoomoneyGatewaySettingsDto):
            raise TypeError("YoomoneyGateway requires YoomoneyGatewaySettingsDto")

        self._client = self._make_client(base_url=self.API_BASE)

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        payment_id = str(uuid.uuid4())
        payload = await self._create_payment_payload(str(amount), details, payment_id)
        query = self.API_BASE
        for value in payload:
            query += str(value).replace("_", "-") + "=" + str(payload[value])
            query += "&"
        query = query[:-1].replace(" ", "%20")

        try:
            response = await self._client.post(query, follow_redirects=True)
            if response.status_code != 302:
                response.raise_for_status()
            return self._get_payment_data(response.url, payment_id)

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
            payment_id_str = payment_object.get("label")

            if not payment_id_str:
                raise ValueError("Required field 'id' is missing")

            if not self.verify_notification(payment_object):
                raise ValueError("YooMoney verification failed.")

            try:
                payment_id = UUID(payment_id_str)
            except ValueError:
                raise ValueError("Invalid UUID format for payment ID")

            transaction_status = TransactionStatus.COMPLETED

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def _create_payment_payload(self, amount: str, details: str, label: str) -> dict[str, Any]:
        return {
            "receiver": self.gateway.settings.wallet_id,
            "quickpay_form": self.PAY_FORM,
            "targets": details,
            "paymentType": self.PAY_TYPE,
            "sum": amount,
            "label": label,
            "successURL": await self._get_bot_redirect_url(),
        }

    def _get_payment_data(self, payment_url: URL, payment_id: str) -> PaymentResult:
        if not payment_url:
            raise KeyError("Invalid response from Yoomoney API: missing 'url'")

        return PaymentResult(id=UUID(payment_id), url=str(payment_url))

    def verify_notification(self, data: dict) -> bool:
        params = [
            data.get("notification_type", ""),
            data.get("operation_id", ""),
            data.get("amount", ""),
            data.get("currency", ""),
            data.get("datetime", ""),
            data.get("sender", ""),
            data.get("codepro", ""),
            self.gateway.settings.secret_key.get_secret_value(),
            data.get("label", ""),
        ]

        sign_str = "&".join(params)
        computed_hash = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

        is_valid = computed_hash == data.get("sha1_hash", "")
        if not is_valid:
            logger.warning(
                f"Invalid signature. Expected {computed_hash}, received {data.get('sha1_hash')}."
            )

        return is_valid
