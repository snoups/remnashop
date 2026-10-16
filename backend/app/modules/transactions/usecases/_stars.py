from typing import Optional

from app.core.enums import Currency, PaymentGatewayType
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.telegram_stars import stars_amount
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository


async def find_matching_stars_order(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    *,
    telegram_id: int,
    payload: str,
    currency: str,
    total_amount: int,
) -> Optional[TransactionDto]:
    order = await transaction_repository.get_by_idempotency_key(
        payload, gateway_type=PaymentGatewayType.TELEGRAM_STARS
    )
    if order is None:
        return None
    user = await user_repository.get_by_telegram_id(telegram_id)
    if (
        user is None
        or order.user_id != user.id
        or currency != Currency.XTR.value
        or total_amount != stars_amount(order)
    ):
        return None
    return order
