from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.connect_guide.dto import ConnectGuideDto
from app.modules.connect_guide.repository import ConnectGuideRepository


class GetConnectGuideUseCase(UseCase[None, ConnectGuideDto]):
    required_permission = Permission.CONNECT_GUIDE_VIEW

    def __init__(self, connect_guide_repository: ConnectGuideRepository, uow: UnitOfWork) -> None:
        self._connect_guide_repository = connect_guide_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> ConnectGuideDto:
        async with self._uow:
            return await self._connect_guide_repository.get()
