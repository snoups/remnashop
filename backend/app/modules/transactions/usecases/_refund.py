from typing import Optional

from app.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from app.modules.subscriptions import PurchaseRollbackDto
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto


def refund_refusal(
    order: TransactionDto, payer: Optional[UserDto], bot_configured: bool
) -> Optional[str]:
    if order.status is not TransactionStatus.PAID:
        return "not_paid"
    if order.gateway_type is not PaymentGatewayType.TELEGRAM_STARS:
        return "not_stars"
    if order.is_test:
        return "test_order"
    if not order.external_payment_id:
        return "no_charge_id"
    if payer is None or payer.telegram_id is None:
        return "no_telegram_id"
    if not bot_configured:
        return "bot_not_configured"
    return None


async def rollback_input(
    transaction_repository: TransactionRepository, order: TransactionDto
) -> PurchaseRollbackDto:
    has_later_paid_order = False
    if (
        order.fulfilled_subscription_id is not None
        and order.created_at is not None
        and order.purchase_type in (PurchaseType.NEW, PurchaseType.CHANGE)
    ):
        has_later_paid_order = await transaction_repository.has_later_paid_order(
            order.fulfilled_subscription_id, order.created_at
        )
    return PurchaseRollbackDto(
        purchase_type=order.purchase_type,
        target_subscription_id=order.target_subscription_id,
        fulfilled_subscription_id=order.fulfilled_subscription_id,
        duration_days=order.duration_days,
        price_paid=order.final_price,
        currency=order.currency,
        has_later_paid_order=has_later_paid_order,
    )
