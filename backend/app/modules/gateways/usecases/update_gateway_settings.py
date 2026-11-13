from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways.dto import PaymentGatewayDto, UpdateGatewaySettingsDto
from app.modules.gateways.events import GatewayChangedEvent
from app.modules.gateways.field_catalog import (
    validate_gateway_field_keys,
    validate_gateway_field_values,
)
from app.modules.gateways.repository import GatewayRepository


class UpdateGatewaySettingsUseCase(UseCase[UpdateGatewaySettingsDto, PaymentGatewayDto]):
    required_permission = Permission.GATEWAYS_UPDATE

    def __init__(
        self,
        gateway_repository: GatewayRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._gateway_repository = gateway_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateGatewaySettingsDto) -> PaymentGatewayDto:
        validate_gateway_field_keys(data.type, data.values)
        validate_gateway_field_values(data.type, data.values)
        values = dict(data.values)
        if (
            data.type is PaymentGatewayType.YOOKASSA
            and "recurring_enabled" in values
            and "payment_mode" not in values
        ):
            # Old clients must still be able to turn recurring charges off after a mode was saved.
            values["payment_mode"] = "both" if values["recurring_enabled"] == "true" else "single"

        async with self._uow:
            gateway = await self._gateway_repository.update_settings(data.type, values)
            await self._event_publisher.publish(
                GatewayChangedEvent(
                    actor=actor,
                    action="settings",
                    gateway_type=data.type,
                    changed_fields=sorted(values),
                )
            )
        logger.info(f"{actor.log} Updated settings of gateway '{data.type.value}'")
        return gateway
