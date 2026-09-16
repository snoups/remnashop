from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupSettingsDto
from app.modules.backups.repository import BackupRepository
from app.modules.users import UserDto


class GetBackupSettingsUseCase(UseCase[None, BackupSettingsDto]):
    required_permission = Permission.BACKUPS_SETTINGS_VIEW

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> BackupSettingsDto:
        async with self._uow:
            return await self._backup_repository.get_settings()
