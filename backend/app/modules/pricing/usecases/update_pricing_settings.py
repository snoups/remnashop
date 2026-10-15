from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing.dto import PricingSettingsDto, UpdatePricingSettingsDto
from app.modules.pricing.events import PricingSettingsChangedEvent
from app.modules.pricing.repository import PricingRepository


class UpdatePricingSettingsUseCase(UseCase[UpdatePricingSettingsDto, PricingSettingsDto]):
    required_permission = Permission.PRICING_SETTINGS_MANAGE

    def __init__(
        self,
        pricing_repository: PricingRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._pricing_repository = pricing_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdatePricingSettingsDto) -> PricingSettingsDto:
        async with self._uow:
            before = await self._pricing_repository.get_settings()
            settings = await self._pricing_repository.update_settings(data)
            await self._event_publisher.publish(
                PricingSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, vars(data))
                )
            )
        logger.info(f"{actor.log} Updated pricing settings")
        return settings
