from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto
from app.modules.gateways.repository import GatewaysRepository
from app.modules.users import UserDto


class ToggleGatewayActiveUseCase(UseCase[PaymentGatewayType, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_TOGGLE

    def __init__(self, gateways_repository: GatewaysRepository, uow: UnitOfWork) -> None:
        self._gateways_repository = gateways_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: PaymentGatewayType) -> PaymentGatewayDto:
        async with self._uow:
            current = await self._gateways_repository.get_by_type(data)
            if not current.is_active and not current.is_configured:
                raise ValidationError(f"Gateway '{data.value}' is not configured")

        async with self._uow:
            gateway = await self._gateways_repository.set_active(data, not current.is_active)
        logger.info(
            f"Gateway '{data.value}' active status set to '{gateway.is_active}' "
            f"by actor {actor.log}"
        )
        return gateway
