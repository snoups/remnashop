from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, ReorderGatewaysDto
from app.modules.gateways.events import GatewayChangedEvent
from app.modules.gateways.repository import GatewayRepository


class ReorderGatewaysUseCase(UseCase[ReorderGatewaysDto, list[PaymentGatewayDto]]):
    required_permission = Permission.GATEWAYS_REORDER

    def __init__(
        self,
        gateway_repository: GatewayRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._gateway_repository = gateway_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: ReorderGatewaysDto) -> list[PaymentGatewayDto]:
        all_types = set(PaymentGatewayType)
        if set(data.ordered_types) != all_types or len(data.ordered_types) != len(all_types):
            raise ValidationError(
                "ordered_types must contain every gateway type exactly once",
                code=ErrorCode.GATEWAY_REORDER_INCOMPLETE,
            )

        async with self._uow:
            gateways = await self._gateway_repository.reorder(data.ordered_types)
            await self._event_publisher.publish(GatewayChangedEvent(user=actor, action="reorder"))
        logger.info(f"Gateways reordered by actor {actor.log}")
        return gateways
