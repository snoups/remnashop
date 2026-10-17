from typing import Final

from app.core.enums import DiscountSource, TransactionStatus
from app.modules.transactions.dto import TransactionDto
from app.modules.users import UserRepository

# closed by the gateway (or the expiry sweep) without a payment
UNPAID_FINAL: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.CANCELED, TransactionStatus.FAILED}
)


async def give_back_purchase_discount(
    user_repository: UserRepository, order: TransactionDto
) -> None:
    # the one-shot discount was spent when the order was created; an order
    # nobody paid returns it
    if order.discount_source is not DiscountSource.PURCHASE:
        return
    await user_repository.restore_purchase_discount(
        order.user_id,
        order.discount_percent,
        order.discount_promocode_id,
        from_promocode=order.discount_from_promocode,
    )
