from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository

# Must exceed the longest webhook-resend window of any payment provider --
# deleting a still-resendable key turns a replay into a fresh claim (double
# charge + double provisioning).
IDEMPOTENCY_KEY_RETENTION_DAYS: Final[int] = 7


class PruneIdempotencyKeysUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self, idempotency_repository: PurchaseIdempotencyRepository, uow: UnitOfWork
    ) -> None:
        self._idempotency_repository = idempotency_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            cutoff = datetime_now() - timedelta(days=IDEMPOTENCY_KEY_RETENTION_DAYS)
            (
                purchase_deleted,
                addon_deleted,
            ) = await self._idempotency_repository.delete_stale(cutoff)
        logger.info(
            f"Pruned {purchase_deleted} purchase + {addon_deleted} addon idempotency key(s) "
            f"older than {IDEMPOTENCY_KEY_RETENTION_DAYS}d"
        )
