from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.dto import EmailImageFileDto, GetEmailImageDto
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import email_image_path


class GetBroadcastEmailImageUseCase(UseCase[GetEmailImageDto, EmailImageFileDto]):
    required_permission = Permission.BROADCASTS_EMAIL_IMAGE_VIEW

    def __init__(
        self, broadcast_repository: BroadcastRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetEmailImageDto) -> EmailImageFileDto:
        async with self._uow:
            image = await self._broadcast_repository.find_email_image(
                data.broadcast_id, data.image_id
            )
        if image is None:
            raise NotFoundError(
                f"Image '{data.image_id}' not found", code=ErrorCode.BROADCAST_NOT_FOUND
            )
        path = email_image_path(
            self._config.media_dir, image.broadcast_id, image.id, image.extension
        )
        if not path.is_file():
            raise NotFoundError(
                f"Image '{data.image_id}' not found", code=ErrorCode.BROADCAST_NOT_FOUND
            )
        return EmailImageFileDto(content_type=image.content_type, path=path)
