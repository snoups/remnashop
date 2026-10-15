from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastStatus
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.lifecycle import lock_editable
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import delete_media
from app.modules.broadcasts.validation import validate_texts


class DeleteBroadcastMediaUseCase(UseCase[int, BroadcastDto]):
    required_permission = Permission.BROADCASTS_MEDIA_DELETE

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> BroadcastDto:
        async with self._uow:
            current = await lock_editable(self._broadcast_repository, data)
            validate_texts(current.contents, current.default_locale, has_media=False)
            await self._broadcast_repository.update_fields(
                current.id,
                media_type=None,
                media_content_type=None,
                media_extension=None,
                media_size_bytes=None,
                media_file_id=None,
                status=BroadcastStatus.DRAFT,
                scheduled_at=None,
            )
            updated = await self._broadcast_repository.get_by_id(current.id)
            await self._event_publisher.publish(
                BroadcastChangedEvent(actor=actor, action="delete_media", broadcast_id=current.id)
            )
        if current.media_extension is not None:
            delete_media(
                self._config.media_dir, current.id, current.media_version, current.media_extension
            )
        logger.info(f"{actor.log} Deleted media of broadcast '{current.id}'")
        return updated
