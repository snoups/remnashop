from typing import Optional

from app.core.actor import Actor
from app.modules.transactions.dto import TransactionDto, TransactionWithUserDto
from app.modules.users import UserDto, visible_user


def visible_transaction(
    actor: Actor, order: TransactionDto, user: Optional[UserDto]
) -> TransactionWithUserDto:
    # a staff owner the caller may not see takes the order's contact email with it
    shown = visible_user(actor, user)
    if user is not None and shown is None:
        order = order.model_copy(update={"customer_email": None})
    return TransactionWithUserDto(order=order, user=shown)
