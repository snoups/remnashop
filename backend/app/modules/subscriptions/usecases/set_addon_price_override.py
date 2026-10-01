from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, SetAddOnPriceOverrideDto
from app.modules.subscriptions.events import AddOnChangedEvent


class SetAddOnPriceOverrideUseCase(UseCase[SetAddOnPriceOverrideDto, AddOnDto]):
    required_permission = Permission.ADDONS_PRICE_OVERRIDE_MANAGE

    def __init__(
        self, addon_repository: AddOnRepository, event_publisher: EventPublisher, uow: UnitOfWork
    ) -> None:
        self._addon_repository = addon_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetAddOnPriceOverrideDto) -> AddOnDto:
        async with self._uow:
            addon = await self._addon_repository.set_price_override(data)
            await self._event_publisher.publish(
                AddOnChangedEvent(user=actor, action="price_override", addon_id=data.addon_id)
            )
        logger.info(
            f"{actor.log} Set price override for addon '{data.addon_id}' currency '{data.currency}'"
        )
        return addon
