import hashlib
import uuid
from decimal import Decimal
from hmac import compare_digest
from typing import Any, Final
from urllib.parse import parse_qs, urlencode
from uuid import UUID

from aiogram import Bot
from fastapi import Request
from fastapi.responses import PlainTextResponse
from loguru import logger

from src.application.dto import PaymentGatewayDto, PaymentResultDto
from src.application.dto.payment_gateway import RoboKassaGatewaySettingsDto
from src.core.config import AppConfig
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


# https://docs.robokassa.ru/
class RobokassaGateway(BasePaymentGateway):
    PAYMENT_URL: Final[str] = "https://auth.robokassa.ru/Merchant/Index.aspx"

    SHP_ORDER_ID: Final[str] = "Shp_order_id"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, RoboKassaGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {RoboKassaGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        order_id = uuid.uuid4()
        inv_id = 0
        out_sum = self._format_amount(amount)
        shp_params = {self.SHP_ORDER_ID: str(order_id)}

        signature = self._sign_payment(out_sum, inv_id, shp_params)
        payment_url = self._build_payment_url(
            out_sum=out_sum,
            inv_id=inv_id,
            description=details[:100],
            signature=signature,
            shp_params=shp_params,
        )

        return PaymentResultDto(id=order_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        logger.debug(f"Received {self.__class__.__name__} webhook request")

        webhook_data = await self._parse_request_data(request)

        if not self._verify_webhook(webhook_data):
            raise PermissionError("Webhook verification failed")

        order_id_str = webhook_data.get(self.SHP_ORDER_ID)

        if not order_id_str:
            raise ValueError(f"Required field '{self.SHP_ORDER_ID}' is missing")

        payment_id = UUID(order_id_str)

        return payment_id, TransactionStatus.COMPLETED

    async def build_webhook_response(self, request: Request) -> PlainTextResponse:
        data = await self._parse_request_data(request)
        inv_id = data.get("InvId", "")
        return PlainTextResponse(content=f"OK{inv_id}")

    async def _parse_request_data(self, request: Request) -> dict[str, str]:
        body = await request.body()
        if body:
            parsed = {
                key: values[0]
                for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()
                if values
            }
            if parsed:
                return parsed

        return dict(request.query_params)

    def _sign_payment(
        self,
        out_sum: str,
        inv_id: int,
        shp_params: dict[str, str],
    ) -> str:
        merchant_login = self.data.settings.merchant_login  # type: ignore[union-attr]

        password1 = self.data.settings.password1.get_secret_value()  # type: ignore[union-attr]

        if not merchant_login or not password1:
            raise ValueError("merchant_login and password1 are required")

        parts: list[str] = [
            merchant_login,
            out_sum,
            str(inv_id),
            password1,
        ]
        parts.extend(f"{k}={shp_params[k]}" for k in sorted(shp_params))
        return self._hash(":".join(parts))

    def _sign_webhook(
        self,
        out_sum: str,
        inv_id: str,
        shp_params: dict[str, str],
    ) -> str:
        parts = [
            out_sum,
            inv_id,
            self.data.settings.password2.get_secret_value(),  # type: ignore[union-attr]
        ]
        parts.extend(f"{k}={shp_params[k]}" for k in sorted(shp_params))
        return self._hash(":".join(parts))

    @staticmethod
    def _hash(raw: str, algorithm: str = "md5") -> str:
        algo = algorithm.lower().replace("-", "")
        return hashlib.new(algo, raw.encode("utf-8")).hexdigest().upper()

    def _verify_webhook(self, data: dict[str, str]) -> bool:
        received_sign = data.get("SignatureValue", "").upper()
        out_sum = data.get("OutSum", "")
        inv_id = data.get("InvId", "")

        if not received_sign or not out_sum or not inv_id:
            logger.warning("Webhook is missing required fields (OutSum / InvId / SignatureValue)")
            return False

        shp_params = {k: v for k, v in data.items() if k.startswith("Shp_")}

        if not shp_params.get(self.SHP_ORDER_ID):
            logger.warning(f"Webhook is missing '{self.SHP_ORDER_ID}' field")
            return False

        expected = self._sign_webhook(out_sum, inv_id, shp_params)

        if not compare_digest(expected, received_sign):
            logger.warning("Invalid Robokassa webhook signature")
            return False

        return True

    def _build_payment_url(
        self,
        out_sum: str,
        inv_id: int,
        description: str,
        signature: str,
        shp_params: dict[str, str],
    ) -> str:
        params: dict[str, Any] = {
            "MerchantLogin": self.data.settings.merchant_login,  # type: ignore[union-attr]
            "OutSum": out_sum,
            "InvId": inv_id,
            "Description": description,
            "SignatureValue": signature,
            "Culture": "ru",
            "Encoding": "utf-8",
            **shp_params,
        }

        return f"{self.PAYMENT_URL}?{urlencode(params)}"

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")
