from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto, SaveBroadcastDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.validation import (
    assert_references,
    validate_audience,
    validate_broadcast,
)
from app.modules.promocodes import PromocodeRepository


class CreateBroadcastUseCase(UseCase[SaveBroadcastDto, BroadcastDto]):
    required_permission = Permission.BROADCASTS_CREATE

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        promocode_repository: PromocodeRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._promocode_repository = promocode_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SaveBroadcastDto) -> BroadcastDto:
        validate_audience(data.audience)
        validate_broadcast(data, has_media=False)
        async with self._uow:
            await assert_references(data, self._broadcast_repository, self._promocode_repository)
            created = await self._broadcast_repository.create(
                data, created_by=actor.id if actor.id > 0 else None
            )
            await self._event_publisher.publish(
                BroadcastChangedEvent(user=actor, action="create", broadcast_id=created.id)
            )
        logger.info(f"{actor.log} Created broadcast '{created.id}'")
        return created
