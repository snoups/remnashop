from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import BroadcastSummaryDto
from app.modules.broadcasts.repository import BroadcastRepository


class GetBroadcastSummaryUseCase(UseCase[None, BroadcastSummaryDto]):
    required_permission = Permission.BROADCASTS_SUMMARY_VIEW

    def __init__(self, broadcast_repository: BroadcastRepository, uow: UnitOfWork) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> BroadcastSummaryDto:
        async with self._uow:
            return await self._broadcast_repository.summary(datetime_now())
