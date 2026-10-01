from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, SetAddOnBasePriceDto
from app.modules.subscriptions.events import AddOnChangedEvent


class SetAddOnBasePriceUseCase(UseCase[SetAddOnBasePriceDto, AddOnDto]):
    required_permission = Permission.ADDONS_PRICES_MANAGE

    def __init__(
        self, addon_repository: AddOnRepository, event_publisher: EventPublisher, uow: UnitOfWork
    ) -> None:
        self._addon_repository = addon_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetAddOnBasePriceDto) -> AddOnDto:
        async with self._uow:
            addon = await self._addon_repository.set_base_price(data)
            await self._event_publisher.publish(
                AddOnChangedEvent(user=actor, action="base_price", addon_id=data.addon_id)
            )
        logger.info(f"{actor.log} Set base price for addon '{data.addon_id}'")
        return addon
