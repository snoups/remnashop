from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions import (
    PurchaseIdempotencyRepository,
    PurchaseSubscriptionDispatch,
)
from app.modules.transactions.dto import ReconcilePaidTransactionsDto
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.repository import RECONCILE_WINDOW, TransactionRepository


class ReconcilePaidTransactionsUseCase(UseCase[ReconcilePaidTransactionsDto, None]):
    required_permission = None

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
        uow: UnitOfWork,
        purchase_dispatch: PurchaseSubscriptionDispatch,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._idempotency_repository = idempotency_repository
        self._uow = uow
        self._purchase_dispatch = purchase_dispatch

    async def _execute(self, actor: Actor, data: ReconcilePaidTransactionsDto) -> None:
        now = datetime_now()
        stuck = await self._transaction_repository.list_paid_awaiting_reconciliation(
            now - data.grace_period, since=now - RECONCILE_WINDOW
        )

        redispatched = 0
        for order in stuck:
            linked = await self._idempotency_repository.get_subscription_id(order.idempotency_key)
            if linked is not None:
                async with self._uow:
                    await self._transaction_repository.mark_fulfilled(order.id, linked)
                continue

            # same idempotency_key as the original attempt: the purchase locks the
            # key before writing, so only one of them provisions the order
            await dispatch_fulfillment(self._purchase_dispatch, order)
            redispatched += 1

        logger.info(
            f"Reconciliation sweep: {redispatched} of {len(stuck)} stuck PAID transaction(s) "
            f"redispatched"
        )
