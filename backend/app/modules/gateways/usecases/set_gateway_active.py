from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, SetGatewayActiveDto
from app.modules.gateways.events import GatewayChangedEvent
from app.modules.gateways.repository import GatewayRepository


class SetGatewayActiveUseCase(UseCase[SetGatewayActiveDto, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_ACTIVE_SET

    def __init__(
        self,
        gateway_repository: GatewayRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._gateway_repository = gateway_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetGatewayActiveDto) -> PaymentGatewayDto:
        async with self._uow:
            current = await self._gateway_repository.get_by_type(data.type)
            if data.is_active and not current.is_configured:
                raise ValidationError(
                    f"Gateway '{data.type.value}' is not configured",
                    code=ErrorCode.GATEWAY_NOT_CONFIGURED,
                )

            gateway = await self._gateway_repository.set_active(data.type, data.is_active)
            await self._event_publisher.publish(
                GatewayChangedEvent(
                    actor=actor,
                    action="enable" if data.is_active else "disable",
                    gateway_type=data.type,
                    is_active=gateway.is_active,
                )
            )
        logger.info(
            f"{actor.log} {'Enabled' if gateway.is_active else 'Disabled'} gateway "
            f"'{data.type.value}'"
        )
        return gateway
