from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.repository import BroadcastRepository


class GetBroadcastUseCase(UseCase[int, BroadcastDto]):
    required_permission = Permission.BROADCASTS_DETAIL_VIEW

    def __init__(self, broadcast_repository: BroadcastRepository, uow: UnitOfWork) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> BroadcastDto:
        async with self._uow:
            return await self._broadcast_repository.get_or_raise(data)
