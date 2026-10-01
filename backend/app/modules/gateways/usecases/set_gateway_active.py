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
from app.modules.gateways.repository import GatewaysRepository


class SetGatewayActiveUseCase(UseCase[SetGatewayActiveDto, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_ACTIVE_SET

    def __init__(
        self,
        gateways_repository: GatewaysRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._gateways_repository = gateways_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetGatewayActiveDto) -> PaymentGatewayDto:
        async with self._uow:
            current = await self._gateways_repository.get_by_type(data.type)
            if data.is_active and not current.is_configured:
                raise ValidationError(
                    f"Gateway '{data.type.value}' is not configured",
                    code=ErrorCode.GATEWAY_NOT_CONFIGURED,
                )

        async with self._uow:
            gateway = await self._gateways_repository.set_active(data.type, data.is_active)
            await self._event_publisher.publish(
                GatewayChangedEvent(
                    user=actor,
                    action="enable" if data.is_active else "disable",
                    gateway_type=data.type.value,
                    is_active=gateway.is_active,
                )
            )
        logger.info(
            f"Gateway '{data.type.value}' active status set to '{gateway.is_active}' "
            f"by actor {actor.log}"
        )
        return gateway
