from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, UpdateGatewaySettingsDto
from app.modules.gateways.events import GatewayChangedEvent
from app.modules.gateways.field_catalog import (
    validate_gateway_field_keys,
    validate_gateway_field_values,
)
from app.modules.gateways.repository import GatewaysRepository


class UpdateGatewaySettingsUseCase(UseCase[UpdateGatewaySettingsDto, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_UPDATE

    def __init__(
        self,
        gateways_repository: GatewaysRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._gateways_repository = gateways_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateGatewaySettingsDto) -> PaymentGatewayDto:
        validate_gateway_field_keys(data.type, data.values)
        validate_gateway_field_values(data.type, data.values)

        async with self._uow:
            gateway = await self._gateways_repository.update_settings(data.type, data.values)
            await self._event_publisher.publish(
                GatewayChangedEvent(
                    user=actor,
                    action="settings",
                    gateway_type=data.type.value,
                    changed_fields=sorted(data.values),
                )
            )
        logger.info(f"Gateway '{data.type.value}' settings updated by actor {actor.log}")
        return gateway
