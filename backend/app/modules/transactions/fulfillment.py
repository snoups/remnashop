from functools import partial

from app.core.db.uow import UnitOfWork
from app.core.enums import TransactionStatus
from app.modules.subscriptions import PurchaseSubscriptionDispatch
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import ProviderPayment
from app.modules.transactions.repository import TransactionRepository


async def settle_verified_payment(
    order: TransactionDto,
    payment: ProviderPayment,
    repository: TransactionRepository,
    uow: UnitOfWork,
    dispatch: PurchaseSubscriptionDispatch,
) -> bool:
    async with uow:
        moved = await repository.mark_status_if(
            order.id,
            TransactionStatus.PAID,
            current=frozenset({order.status}),
            external_payment_id=payment.provider_payment_id or order.external_payment_id,
        )
        if not moved:
            return False
        await repository.remember_payment_method(
            order.id, payment.saved_payment_method_id, payment.payment_method_shop_id
        )
        if not order.is_test:
            await uow.after_commit(partial(dispatch_fulfillment, dispatch, order))
    return True


async def dispatch_fulfillment(
    dispatch: PurchaseSubscriptionDispatch, order: TransactionDto
) -> None:
    # Keyed by the order's idempotency_key, so a redispatch of the same order
    # provisions it once.
    await dispatch.kiq(
        user_id=order.user_id,
        plan_snapshot=order.plan_snapshot.to_json(),
        duration_days=order.duration_days,
        price_paid=str(order.final_price),
        base_price=str(order.base_price),
        currency=order.currency.value,
        purchase_type=order.purchase_type.value,
        target_subscription_id=order.target_subscription_id,
        idempotency_key=order.idempotency_key,
    )
