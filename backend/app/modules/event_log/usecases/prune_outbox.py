from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.event_log.outbox_repository import EventOutboxRepository

_OUTBOX_RETENTION_DAYS: Final[int] = 14


class PruneOutboxUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, outbox_repository: EventOutboxRepository, uow: UnitOfWork) -> None:
        self._outbox_repository = outbox_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            cutoff = datetime_now() - timedelta(days=_OUTBOX_RETENTION_DAYS)
            deleted = await self._outbox_repository.delete_processed_before(cutoff)
            poisoned = await self._outbox_repository.count_poisoned()
        logger.info(
            f"Pruned {deleted} processed outbox row(s) older than {_OUTBOX_RETENTION_DAYS}d; "
            f"{poisoned} poisoned row(s) remain unprocessed"
        )
