from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.events import PromocodeChangedEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserRepository


class DeletePromocodeUseCase(UseCase[int, None]):
    required_permission = Permission.PROMOCODES_DELETE

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._user_repository.clear_discounts_from({data})
            await self._promocode_repository.delete(data)
            await self._event_publisher.publish(
                PromocodeChangedEvent(user=actor, action="delete", promocode_id=data)
            )
        logger.info(f"{actor.log} Deleted promocode '{data}'")
