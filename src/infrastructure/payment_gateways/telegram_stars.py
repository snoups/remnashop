from decimal import Decimal
from uuid import UUID

from aiogram.types import LabeledPrice
from fastapi import Request
from loguru import logger

from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


class TelegramStarsGateway(BasePaymentGateway):
    async def handle_create_payment(self, payment_id: str, amount: Decimal, details: str) -> str:
        prices = [LabeledPrice(label=self.gateway.currency, amount=int(amount))]

        try:
            pay_url = await self.bot.create_invoice_link(
                title=details[:32],
                description=details[:255],
                payload=payment_id,
                currency=self.gateway.currency,
                prices=prices,
            )

            return pay_url

        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        raise NotImplementedError
