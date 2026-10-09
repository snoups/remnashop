from functools import partial
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DiscountSource, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions import PurchaseIdempotencyRepository, PurchaseSubscriptionDispatch
from app.modules.transactions.dto import TransactionWithUserDto
from app.modules.transactions.events import TransactionFulfilledManuallyEvent
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.visibility import visible_transaction
from app.modules.users import UserRepository

# the gateway reported no payment, the admin confirms it was received after all
_UNPAID_FINAL: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.FAILED, TransactionStatus.CANCELED}
)


class FulfillTransactionUseCase(UseCase[int, TransactionWithUserDto]):
    required_permission = Permission.TRANSACTIONS_FULFILL

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
        user_repository: UserRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        purchase_dispatch: PurchaseSubscriptionDispatch,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._idempotency_repository = idempotency_repository
        self._user_repository = user_repository
        self._event_publisher = event_publisher
        self._uow = uow
        self._purchase_dispatch = purchase_dispatch

    async def _execute(self, actor: Actor, data: int) -> TransactionWithUserDto:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
            user = await self._user_repository.get_by_id(order.user_id)
            unpaid = order.status in _UNPAID_FINAL
            unfulfilled = order.status is TransactionStatus.PAID and order.fulfilled_at is None
            if order.is_test or user is None or not (unpaid or unfulfilled):
                raise ConflictError(
                    f"Transaction '{order.id}' can't be fulfilled",
                    code=ErrorCode.PAYMENT_ORDER_NOT_FULFILLABLE,
                )

            linked = await self._idempotency_repository.get_subscription_id(order.idempotency_key)
            if linked is not None:
                # already provisioned, the reconciliation sweep just hasn't recorded it
                await self._transaction_repository.mark_fulfilled(order.id, linked)
            else:
                if unpaid:
                    changed = await self._transaction_repository.mark_status_if(
                        order.id, TransactionStatus.PAID, current=_UNPAID_FINAL
                    )
                    if not changed:
                        raise ConflictError(
                            f"Transaction '{order.id}' changed status meanwhile",
                            code=ErrorCode.PAYMENT_ORDER_NOT_FULFILLABLE,
                        )
                    if order.discount_source is DiscountSource.PURCHASE:
                        # handed back on cancel; a no-op once spent elsewhere
                        await self._user_repository.spend_purchase_discount(
                            order.user_id, order.discount_percent
                        )
                await self._event_publisher.publish(
                    TransactionFulfilledManuallyEvent(
                        actor=actor,
                        target=user,
                        order_id=order.id,
                        previous_status=order.status.value,
                    )
                )
                await self._uow.after_commit(
                    partial(dispatch_fulfillment, self._purchase_dispatch, order)
                )
                logger.info(
                    f"Transaction '{order.id}' ({order.status.value}) fulfilled manually "
                    f"by '{actor.id}'"
                )

        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
        return visible_transaction(actor, order, user)
