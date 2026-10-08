from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto, UpdateBroadcastDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.usecases.editable import lock_editable
from app.modules.broadcasts.validation import (
    assert_references,
    validate_audience,
    validate_broadcast,
)
from app.modules.promocodes import PromocodeRepository


class UpdateBroadcastUseCase(UseCase[UpdateBroadcastDto, BroadcastDto]):
    required_permission = Permission.BROADCASTS_UPDATE

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

    async def _execute(self, actor: Actor, data: UpdateBroadcastDto) -> BroadcastDto:
        async with self._uow:
            current = await lock_editable(self._broadcast_repository, data.broadcast_id)
            validate_audience(data.data.audience)
            validate_broadcast(data.data, has_media=current.has_media)
            await assert_references(
                data.data, self._broadcast_repository, self._promocode_repository
            )
            updated = await self._broadcast_repository.replace(current.id, data.data)
            await self._event_publisher.publish(
                BroadcastChangedEvent(user=actor, action="update", broadcast_id=current.id)
            )
        logger.info(f"{actor.log} Updated broadcast '{current.id}'")
        return updated
