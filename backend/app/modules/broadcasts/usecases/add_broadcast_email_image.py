from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import AddEmailImageDto, EmailImageDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.lifecycle import lock_editable
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import (
    EMAIL_IMAGE_TYPES,
    MAX_EMAIL_IMAGE_BYTES,
    MAX_EMAIL_IMAGES,
    email_image_path,
)


class AddBroadcastEmailImageUseCase(UseCase[AddEmailImageDto, EmailImageDto]):
    required_permission = Permission.BROADCASTS_EMAIL_IMAGE_ADD

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

    async def _execute(self, actor: Actor, data: AddEmailImageDto) -> EmailImageDto:
        extension = EMAIL_IMAGE_TYPES.get(data.content_type)
        if extension is None:
            raise ValidationError(
                f"Unsupported image type: {data.content_type}",
                code=ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID,
            )
        if data.size <= 0 or data.size > MAX_EMAIL_IMAGE_BYTES:
            raise ValidationError(
                f"Image size must be between 1 byte and {MAX_EMAIL_IMAGE_BYTES} bytes",
                code=ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID,
            )

        async with self._uow:
            current = await lock_editable(self._broadcast_repository, data.broadcast_id)
            existing = await self._broadcast_repository.list_email_images(current.id)
            if len(existing) >= MAX_EMAIL_IMAGES:
                raise ValidationError(
                    f"A broadcast takes at most {MAX_EMAIL_IMAGES} images",
                    code=ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID,
                )
            image = await self._broadcast_repository.add_email_image(
                current.id, data.content_type, extension, data.size
            )
            await self._event_publisher.publish(
                BroadcastChangedEvent(
                    actor=actor, action="add_email_image", broadcast_id=current.id
                )
            )
        # the file lands only after the row commits
        path = email_image_path(self._config.media_dir, current.id, image.id, extension)
        path.parent.mkdir(parents=True, exist_ok=True)
        data.source.replace(path)
        logger.info(f"{actor.log} Added email image '{image.id}' to broadcast '{current.id}'")
        return image
