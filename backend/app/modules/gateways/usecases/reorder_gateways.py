from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, ReorderGatewaysDto
from app.modules.gateways.repository import GatewaysRepository
from app.modules.users import UserDto


class ReorderGatewaysUseCase(UseCase[ReorderGatewaysDto, list[PaymentGatewayDto]]):
    required_permission = Permission.GATEWAYS_REORDER

    def __init__(self, gateways_repository: GatewaysRepository, uow: UnitOfWork) -> None:
        self._gateways_repository = gateways_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ReorderGatewaysDto) -> list[PaymentGatewayDto]:
        all_types = set(PaymentGatewayType)
        if set(data.ordered_types) != all_types or len(data.ordered_types) != len(all_types):
            raise ValidationError("ordered_types must contain every gateway type exactly once")

        async with self._uow:
            gateways = await self._gateways_repository.reorder(data.ordered_types)
        logger.info(f"Gateways reordered by actor {actor.log}")
        return gateways
