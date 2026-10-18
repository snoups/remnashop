from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.retention import SHORT_RETENTION

# rows per delete: each batch is its own short transaction
_BATCH: Final[int] = 5_000


class PruneEventLogUseCase(UseCase[None, int]):
    required_permission = None

    def __init__(self, event_log_repository: EventLogRepository, uow: UnitOfWork) -> None:
        self._event_log_repository = event_log_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> int:
        cutoff = datetime_now() - SHORT_RETENTION
        total = 0
        while True:
            async with self._uow:
                deleted = await self._event_log_repository.delete_short_retention_before(
                    cutoff, limit=_BATCH
                )
            total += deleted
            if deleted < _BATCH:
                break
        logger.info(f"{actor.log} Pruned {total} short-retention event log entr(ies)")
        return total
