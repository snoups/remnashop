from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto
from app.modules.gateways.repository import GatewaysRepository
from app.modules.users import UserDto


class ListGatewaysUseCase(UseCase[None, list[PaymentGatewayDto]]):
    required_permission = Permission.GATEWAYS_VIEW

    def __init__(self, gateways_repository: GatewaysRepository) -> None:
        self._gateways_repository = gateways_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PaymentGatewayDto]:
        return await self._gateways_repository.get_all()
