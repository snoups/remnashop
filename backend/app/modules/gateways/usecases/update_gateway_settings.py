from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, UpdateGatewaySettingsDto
from app.modules.gateways.field_catalog import validate_gateway_field_keys
from app.modules.gateways.repository import GatewaysRepository
from app.modules.users import UserDto


class UpdateGatewaySettingsUseCase(UseCase[UpdateGatewaySettingsDto, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_UPDATE

    def __init__(self, gateways_repository: GatewaysRepository, uow: UnitOfWork) -> None:
        self._gateways_repository = gateways_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateGatewaySettingsDto) -> PaymentGatewayDto:
        validate_gateway_field_keys(data.type, data.values)

        async with self._uow:
            gateway = await self._gateways_repository.update_settings(data.type, data.values)
        logger.info(f"Gateway '{data.type.value}' settings updated by actor {actor.log}")
        return gateway
