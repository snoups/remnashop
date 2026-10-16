from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto, UpdateBroadcastDto
from app.modules.broadcasts.email_html import email_image_ids
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.lifecycle import lock_editable
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import delete_email_images
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
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._promocode_repository = promocode_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateBroadcastDto) -> BroadcastDto:
        async with self._uow:
            current = await lock_editable(self._broadcast_repository, data.broadcast_id)
            validate_audience(data.data.audience)
            images = await self._broadcast_repository.list_email_images(current.id)
            validate_broadcast(
                data.data,
                has_media=current.has_media,
                images={image.id: image.size_bytes for image in images},
            )
            await assert_references(
                data.data, self._broadcast_repository, self._promocode_repository
            )
            updated = await self._broadcast_repository.replace(current.id, data.data)
            referenced = set().union(
                *(email_image_ids(content.html) for content in data.data.email_contents.values())
            )
            unused = [image for image in images if image.id not in referenced]
            await self._broadcast_repository.delete_email_images([image.id for image in unused])
            await self._event_publisher.publish(
                BroadcastChangedEvent(actor=actor, action="update", broadcast_id=current.id)
            )
        delete_email_images(self._config.media_dir, current.id, unused)
        logger.info(f"{actor.log} Updated broadcast '{current.id}'")
        return updated
