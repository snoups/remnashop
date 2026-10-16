from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import delete_all_email_images, delete_media


class DeleteBroadcastUseCase(UseCase[int, None]):
    required_permission = Permission.BROADCASTS_DELETE

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

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            current = await self._broadcast_repository.get_by_id_for_update(data)
            if current.status is BroadcastStatus.SENDING:
                raise ConflictError(
                    f"Broadcast '{data}' is being sent", code=ErrorCode.BROADCAST_INVALID_STATUS
                )
            await self._broadcast_repository.delete(data)
            await self._event_publisher.publish(
                BroadcastChangedEvent(actor=actor, action="delete", broadcast_id=data)
            )
        if current.media_extension is not None:
            delete_media(
                self._config.media_dir, data, current.media_version, current.media_extension
            )
        delete_all_email_images(self._config.media_dir, data)
        logger.info(f"{actor.log} Deleted broadcast '{data}'")
