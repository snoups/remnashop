from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions import (
    PurchaseIdempotencyRepository,
    PurchaseSubscriptionDispatch,
)
from app.modules.transactions.dto import ReconcilePaidTransactionsDto, TransactionDto
from app.modules.transactions.events import PaidOrderNotFulfilledEvent
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
        event_publisher: EventPublisher,
        redis: Redis,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._idempotency_repository = idempotency_repository
        self._uow = uow
        self._purchase_dispatch = purchase_dispatch
        self._event_publisher = event_publisher
        self._redis = redis

    async def _execute(self, actor: Actor, data: ReconcilePaidTransactionsDto) -> None:
        now = datetime_now()
        async with self._uow:
            stuck = await self._transaction_repository.list_paid_awaiting_reconciliation(
                now - data.grace_period, since=now - RECONCILE_WINDOW
            )

        redispatched = 0
        for order in stuck:
            async with self._uow:
                linked = await self._idempotency_repository.get_subscription_id(
                    order.idempotency_key
                )
                if linked is not None:
                    await self._transaction_repository.mark_fulfilled(order.id, linked)
            if linked is not None:
                continue

            # same idempotency_key as the original attempt: the purchase locks the
            # key before writing, so only one of them provisions the order
            await dispatch_fulfillment(self._purchase_dispatch, order)
            redispatched += 1
            await self._report_once(order)

        logger.info(
            f"Reconciliation sweep: {redispatched} of {len(stuck)} stuck PAID transaction(s) "
            f"redispatched"
        )

    async def _report_once(self, order: TransactionDto) -> None:
        # admins and the customer hear about a stuck order once; the sweep
        # itself keeps retrying it until it goes through or leaves the window
        key = f"{REDIS_KEY_PREFIX}paid_not_fulfilled_reported:{order.id}"
        if not await self._redis.set(key, "1", nx=True, ex=int(RECONCILE_WINDOW.total_seconds())):
            return
        async with self._uow:
            await self._event_publisher.publish(
                PaidOrderNotFulfilledEvent(
                    order_id=order.id,
                    user_id=order.user_id,
                    gateway_type=order.gateway_type.value,
                    amount=str(order.final_price),
                    currency=order.currency.value,
                )
            )
        logger.warning(f"Paid order '{order.id}' is still not fulfilled; reported")
