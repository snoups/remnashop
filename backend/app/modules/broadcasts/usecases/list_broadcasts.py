from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto, ListBroadcastsDto
from app.modules.broadcasts.repository import BroadcastRepository


class ListBroadcastsUseCase(UseCase[ListBroadcastsDto, tuple[list[BroadcastDto], int]]):
    required_permission = Permission.BROADCASTS_VIEW

    def __init__(self, broadcast_repository: BroadcastRepository, uow: UnitOfWork) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListBroadcastsDto
    ) -> tuple[list[BroadcastDto], int]:
        async with self._uow:
            return await self._broadcast_repository.list(data)
