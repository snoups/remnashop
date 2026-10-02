from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DiscountSource
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository


class PruneExpiredTransactionsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            canceled = await self._transaction_repository.cancel_expired_pending(datetime_now())
            # the one-shot discount was spent when the order was created; an
            # order nobody paid gives it back
            for order in canceled:
                if order.discount_source is DiscountSource.PURCHASE:
                    await self._user_repository.restore_purchase_discount(
                        order.user_id, order.discount_percent, order.discount_promocode_id
                    )
        logger.info(f"Canceled {len(canceled)} unpaid transaction(s) past their expiry")
