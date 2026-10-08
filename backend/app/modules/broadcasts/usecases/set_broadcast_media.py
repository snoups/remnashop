from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastMediaType, BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import BroadcastDto, SetBroadcastMediaDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import delete_media, save_media
from app.modules.broadcasts.usecases.editable import lock_editable
from app.modules.broadcasts.validation import validate_text_lengths

_MB: Final[int] = 1024 * 1024
_TYPES: Final[dict[str, tuple[BroadcastMediaType, str, int]]] = {
    "image/jpeg": (BroadcastMediaType.PHOTO, "jpg", 10 * _MB),
    "image/png": (BroadcastMediaType.PHOTO, "png", 10 * _MB),
    "image/webp": (BroadcastMediaType.PHOTO, "webp", 10 * _MB),
    "image/gif": (BroadcastMediaType.ANIMATION, "gif", 50 * _MB),
    "video/mp4": (BroadcastMediaType.VIDEO, "mp4", 50 * _MB),
    "application/pdf": (BroadcastMediaType.DOCUMENT, "pdf", 50 * _MB),
    "application/zip": (BroadcastMediaType.DOCUMENT, "zip", 50 * _MB),
}
MAX_MEDIA_SIZE_BYTES: Final[int] = 50 * _MB


class SetBroadcastMediaUseCase(UseCase[SetBroadcastMediaDto, BroadcastDto]):
    required_permission = Permission.BROADCASTS_MEDIA_SET

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

    async def _execute(self, actor: Actor, data: SetBroadcastMediaDto) -> BroadcastDto:
        spec = _TYPES.get(data.content_type)
        if spec is None:
            raise ValidationError(
                f"Unsupported media type: {data.content_type}",
                code=ErrorCode.BROADCAST_MEDIA_INVALID,
            )
        media_type, extension, limit = spec
        if not data.data or len(data.data) > limit:
            raise ValidationError(
                f"Media size must be between 1 byte and {limit} bytes",
                code=ErrorCode.BROADCAST_MEDIA_INVALID,
            )

        async with self._uow:
            current = await lock_editable(self._broadcast_repository, data.broadcast_id)
            validate_text_lengths(current.contents, has_media=True)
            version = current.media_version + 1
            await self._broadcast_repository.update_fields(
                current.id,
                media_type=media_type,
                media_content_type=data.content_type,
                media_extension=extension,
                media_version=version,
                media_size_bytes=len(data.data),
                media_file_id=None,
                status=BroadcastStatus.DRAFT,
                scheduled_at=None,
            )
            updated = await self._broadcast_repository.get_or_raise(current.id)
            await self._event_publisher.publish(
                BroadcastChangedEvent(user=actor, action="set_media", broadcast_id=current.id)
            )
        # the file changes only after the row commits
        save_media(self._config.media_dir, current.id, version, extension, data.data)
        if current.media_extension is not None:
            delete_media(
                self._config.media_dir, current.id, current.media_version, current.media_extension
            )
        logger.info(f"{actor.log} Set media of broadcast '{current.id}'")
        return updated
