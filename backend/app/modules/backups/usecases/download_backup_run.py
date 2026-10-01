from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupRunDto
from app.modules.backups.repository import BackupRepository


class DownloadBackupRunUseCase(UseCase[int, BackupRunDto]):
    required_permission = Permission.BACKUPS_RUN_DOWNLOAD

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> BackupRunDto:
        async with self._uow:
            return await self._backup_repository.get_run(data)
