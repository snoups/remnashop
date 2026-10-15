from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import AddOnDto, SetAddOnPriceOverrideDto
from app.modules.plans.events import AddOnChangedEvent
from app.modules.pricing import PricingRepository, assert_overridable_currency


class SetAddOnPriceOverrideUseCase(UseCase[SetAddOnPriceOverrideDto, AddOnDto]):
    required_permission = Permission.ADDONS_PRICE_OVERRIDE_MANAGE

    def __init__(
        self,
        addon_repository: AddOnRepository,
        pricing_repository: PricingRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._addon_repository = addon_repository
        self._pricing_repository = pricing_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetAddOnPriceOverrideDto) -> AddOnDto:
        async with self._uow:
            if data.price is not None:  # clearing stays allowed, e.g. after an anchor switch
                settings = await self._pricing_repository.get_settings()
                assert_overridable_currency(data.currency, settings.anchor_currency)
            addon = await self._addon_repository.set_price_override(data)
            await self._event_publisher.publish(
                AddOnChangedEvent(actor=actor, action="price_override", addon_id=data.addon_id)
            )
        logger.info(
            f"{actor.log} Set price override for addon '{data.addon_id}' currency '{data.currency}'"
        )
        return addon
