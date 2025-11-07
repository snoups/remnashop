from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.core.enums import TransactionStatus
from src.infrastructure.taskiq.broker import broker
from src.services.payment_gateway import PaymentGatewayService
from src.services.transaction import TransactionService


@broker.task()
@inject
async def handle_payment_transaction_task(
    payment_id: UUID,
    payment_status: TransactionStatus,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    match payment_status:
        case TransactionStatus.COMPLETED:
            await payment_gateway_service.handle_payment_succeeded(payment_id)
        case TransactionStatus.CANCELED:
            await payment_gateway_service.handle_payment_canceled(payment_id)


@broker.task(schedule=[{"cron": "*/30 * * * *"}])
@inject
async def cancel_transaction_task(transaction_service: FromDishka[TransactionService]) -> None:
    transactions = await transaction_service.get_by_status(TransactionStatus.PENDING)

    if not transactions:
        logger.debug("No pending transactions found")
        return

    old_transactions = [tx for tx in transactions if tx.has_old]
    logger.debug(f"Found '{len(old_transactions)}' old transactions to cancel")

    for transaction in old_transactions:
        transaction.status = TransactionStatus.CANCELED
        await transaction_service.update(transaction)
        logger.debug(f"Transaction '{transaction.id}' canceled")
