from decimal import Decimal
from uuid import UUID

from fastapi import Request
from loguru import logger

from src.application.dto import PaymentResultDto
from src.core.enums import TransactionStatus

from .base import BasePaymentGateway


class ManualTransferGateway(BasePaymentGateway):
    @property
    def requires_webhook(self) -> bool:
        return False

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResultDto:
        payment_id = UUID.uuid4()
        logger.info(f"Created manual transfer payment '{payment_id}' for amount {amount}")
        return PaymentResultDto(id=payment_id, url=None)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        raise NotImplementedError("Manual transfer does not use webhooks")