from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto
from app.modules.gateways.repository import GatewaysRepository


class ListGatewaysUseCase(UseCase[None, list[PaymentGatewayDto]]):
    required_permission = Permission.GATEWAYS_VIEW

    def __init__(self, gateways_repository: GatewaysRepository, uow: UnitOfWork) -> None:
        self._gateways_repository = gateways_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[PaymentGatewayDto]:
        async with self._uow:
            return await self._gateways_repository.get_all()
