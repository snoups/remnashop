from app.modules.subscriptions import PurchaseSubscriptionDispatch
from app.modules.transactions.dto import TransactionDto


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
        change_credit=str(order.change_credit),
        currency=order.currency.value,
        purchase_type=order.purchase_type.value,
        target_subscription_id=order.target_subscription_id,
        idempotency_key=order.idempotency_key,
    )
