import uuid
from base64 import b64decode
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.application.dto import PaymentGatewayDto, PaymentResultDto
from src.application.dto.payment_gateway import WataGatewaySettingsDto
from src.core.config import AppConfig
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


# https://wata.pro/api/
class WataGateway(BasePaymentGateway):
    _client: AsyncClient

    API_BASE: Final[str] = "https://api.wata.pro/api/h2h"

    _PUBLIC_KEY_TTL_SECONDS: Final[int] = 6 * 60 * 60
    _public_key_pem: bytes | None = None
    _public_key_loaded_at: datetime | None = None

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, WataGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {WataGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Authorization": f"Bearer {self.data.settings.api_key.get_secret_value()}",  # type: ignore[union-attr]
                "Content-Type": "application/json",
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        order_id = str(uuid.uuid4())
        payload = await self._create_payment_payload(amount, details, order_id)
        logger.debug(f"Creating payment payload: {payload}")

        try:
            response = await self._client.post("links", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            return self._get_payment_data(data, order_id)

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

        raw_body = await request.body()

        if not await self._verify_webhook(request, raw_body):
            raise PermissionError("Webhook verification failed")

        webhook_data = orjson.loads(raw_body)

        order_id_str = webhook_data.get("orderId")
        if not order_id_str:
            raise ValueError("Required field 'orderId' is missing")

        status = webhook_data.get("transactionStatus")
        payment_id = UUID(order_id_str)

        match status:
            case "Paid":
                transaction_status = TransactionStatus.COMPLETED
            case "Declined":
                transaction_status = TransactionStatus.CANCELED
            case _:
                raise ValueError(f"Unsupported transactionStatus: {status}")

        return payment_id, transaction_status

    async def _create_payment_payload(
        self,
        amount: Decimal,
        details: str,
        order_id: str,
    ) -> dict[str, Any]:
        redirect_url = await self._get_bot_redirect_url()
        return {
            "type": "OneTime",
            "amount": float(amount),
            "currency": self.data.currency.value,
            "description": details,
            "orderId": order_id,
            "successRedirectUrl": redirect_url,
            "failRedirectUrl": redirect_url,
        }

    def _get_payment_data(self, data: dict[str, Any], order_id: str) -> PaymentResultDto:
        payment_url = data.get("url")
        if not payment_url:
            raise KeyError("Invalid response from API: missing 'url'")

        return PaymentResultDto(id=UUID(order_id), url=str(payment_url))

    async def _fetch_public_key(self, *, force_refresh: bool = False) -> bytes:
        now = datetime.now(timezone.utc)
        cache_valid = (
            self._public_key_pem is not None
            and self._public_key_loaded_at is not None
            and (now - self._public_key_loaded_at).total_seconds() < self._PUBLIC_KEY_TTL_SECONDS
        )
        if cache_valid and not force_refresh:
            return self._public_key_pem  # type: ignore[return-value]

        try:
            response = await self._client.get("public-key")
            response.raise_for_status()
            data = orjson.loads(response.content)
            pem_str: str = data["value"]
            self._public_key_pem = pem_str.encode()
            self._public_key_loaded_at = now
            return self._public_key_pem
        except Exception as e:
            logger.error(f"Failed to fetch WATA public key: {e}")
            raise

    @staticmethod
    def _verify_rsa_signature(
        public_key_pem: bytes,
        signature_bytes: bytes,
        raw_body: bytes,
    ) -> None:
        public_key = serialization.load_pem_public_key(public_key_pem)

        if not isinstance(public_key, RSAPublicKey):
            raise ValueError(f"Expected RSAPublicKey, got {type(public_key).__name__}")

        public_key.verify(
            signature_bytes,
            raw_body,
            padding.PKCS1v15(),
            hashes.SHA512(),
        )

    async def _verify_webhook(self, request: Request, raw_body: bytes) -> bool:
        signature_b64 = request.headers.get("X-Signature")
        if not signature_b64:
            logger.warning("Webhook is missing 'X-Signature' header")
            return False

        signature_bytes = b64decode(signature_b64)

        try:
            public_key_pem = await self._fetch_public_key()
            self._verify_rsa_signature(public_key_pem, signature_bytes, raw_body)
            return True

        except InvalidSignature:
            logger.warning("Invalid WATA webhook RSA signature, retrying with fresh public key")
            try:
                public_key_pem = await self._fetch_public_key(force_refresh=True)
                self._verify_rsa_signature(public_key_pem, signature_bytes, raw_body)
                return True
            except InvalidSignature:
                logger.warning("Invalid WATA webhook RSA signature after key refresh")
                return False
        except Exception as e:
            logger.error(f"WATA webhook verification error: {e}")
            return False
