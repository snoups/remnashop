from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupSettingsDto, UpdateBackupSettingsDto
from app.modules.backups.repository import BackupRepository


class UpdateBackupSettingsUseCase(UseCase[UpdateBackupSettingsDto, BackupSettingsDto]):
    required_permission = Permission.BACKUPS_SETTINGS_MANAGE

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateBackupSettingsDto) -> BackupSettingsDto:
        async with self._uow:
            settings = await self._backup_repository.update_settings(data)
        logger.info(f"Backup settings updated by actor {actor.log}")
        return settings
