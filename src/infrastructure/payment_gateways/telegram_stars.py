import uuid
from decimal import Decimal
from typing import Union
from uuid import UUID

from aiogram.types import LabeledPrice
from fastapi import Request
from loguru import logger

from src.application.dto import PaymentResultDto
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


# https://core.telegram.org/api/stars/
class TelegramStarsGateway(BasePaymentGateway):
    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        prices = [LabeledPrice(label=self.data.currency, amount=int(amount))]
        payment_id = uuid.uuid4()

        try:
            payment_url = await self.bot.create_invoice_link(
                title=details[:32],
                description=details[:255],
                payload=str(payment_id),
                currency=self.data.currency,
                prices=prices,
            )

            return PaymentResultDto(id=payment_id, url=payment_url)

        except Exception as e:
            logger.exception(f"An unexpected error occurred while creating payment: {e}")
            raise

    async def handle_webhook(self, request: Request) -> Union[tuple[UUID, TransactionStatus], None]:
        raise NotImplementedError()
