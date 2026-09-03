from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupRunDto
from app.modules.backups.repository import BackupRepository
from app.modules.users import UserDto


class GetBackupRunUseCase(UseCase[int, BackupRunDto]):
    required_permission = Permission.BACKUPS_RUN_VIEW

    def __init__(self, backup_repository: BackupRepository) -> None:
        self._backup_repository = backup_repository

    async def _execute(self, actor: UserDto, data: int) -> BackupRunDto:
        return await self._backup_repository.get_run(data)
