from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.events import AddOnChangedEvent


class DeleteAddOnUseCase(UseCase[int, None]):
    required_permission = Permission.ADDONS_DELETE

    def __init__(
        self, addon_repository: AddOnRepository, event_publisher: EventPublisher, uow: UnitOfWork
    ) -> None:
        self._addon_repository = addon_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._addon_repository.delete(data)
            await self._event_publisher.publish(
                AddOnChangedEvent(user=actor, action="delete", addon_id=data)
            )
        logger.info(f"{actor.log} Deleted addon '{data}'")
