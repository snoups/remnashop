from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.repository import BroadcastRepository

RECIPIENTS_RETENTION: Final[timedelta] = timedelta(days=90)


class PruneBroadcastRecipientsUseCase(UseCase[None, int]):
    required_permission = None

    def __init__(self, broadcast_repository: BroadcastRepository, uow: UnitOfWork) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> int:
        async with self._uow:
            pruned = await self._broadcast_repository.prune_recipients(
                datetime_now() - RECIPIENTS_RETENTION
            )
        if pruned:
            logger.info(f"Pruned {pruned} broadcast recipient rows")
        return pruned
