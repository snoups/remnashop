from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupSettingsDto
from app.modules.backups.events import BackupChangedEvent
from app.modules.backups.repository import BackupRepository


class ResetBackupSettingsUseCase(UseCase[None, BackupSettingsDto]):
    required_permission = Permission.BACKUPS_SETTINGS_RESET

    def __init__(
        self, backup_repository: BackupRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> BackupSettingsDto:
        async with self._uow:
            settings = await self._backup_repository.reset_settings()
            await self._event_publisher.publish(
                BackupChangedEvent(actor=actor, action="settings_reset")
            )
        logger.info(f"{actor.log} Reset backup settings")
        return settings
