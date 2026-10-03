from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions import (
    IDEMPOTENCY_KEY_RETENTION_DAYS,
    PurchaseIdempotencyRepository,
    PurchaseSubscriptionDispatch,
)
from app.modules.transactions.dto import ReconcilePaidTransactionsDto
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.repository import TransactionRepository

# Must stay inside the idempotency-key retention: past it, a key-less order
# looks unprovisioned and a redispatch would provision it a second time.
_WINDOW: Final[timedelta] = timedelta(days=IDEMPOTENCY_KEY_RETENTION_DAYS - 1)


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
            now - data.grace_period, since=now - _WINDOW
        )

        redispatched = 0
        for order in stuck:
            linked = await self._idempotency_repository.get_subscription_id(order.idempotency_key)
            if linked is not None:
                async with self._uow:
                    await self._transaction_repository.mark_fulfilled(order.id, linked)
                continue

            # same idempotency_key as the original attempt, safe even if it's
            # still running or already succeeded
            await dispatch_fulfillment(self._purchase_dispatch, order)
            redispatched += 1

        logger.info(
            f"Reconciliation sweep: {redispatched} of {len(stuck)} stuck PAID transaction(s) "
            f"redispatched"
        )
