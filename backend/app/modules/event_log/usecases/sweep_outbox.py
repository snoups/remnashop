from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.modules.event_log.outbox_repository import EventOutboxRepository, OutboxLagStats
from app.modules.event_log.usecases.process_outbox_entry import ProcessOutboxEntryUseCase

_BATCH_SIZE: Final[int] = 100


class SweepOutboxUseCase(UseCase[None, OutboxLagStats]):
    required_permission = None

    def __init__(
        self,
        outbox_repository: EventOutboxRepository,
        process_entry_use_case: ProcessOutboxEntryUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._outbox_repository = outbox_repository
        self._process_entry_use_case = process_entry_use_case
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> OutboxLagStats:
        async with self._uow:
            entry_ids = await self._outbox_repository.list_unprocessed_ids(limit=_BATCH_SIZE)
            lag = await self._outbox_repository.get_lag_stats()
        for entry_id in entry_ids:
            await self._process_entry_use_case.system(entry_id)
        return lag
