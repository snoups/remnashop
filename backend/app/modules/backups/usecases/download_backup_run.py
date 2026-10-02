from pathlib import Path

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupRunStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.repository import BackupRepository


class DownloadBackupRunUseCase(UseCase[int, Path]):
    required_permission = Permission.BACKUPS_RUN_DOWNLOAD

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> Path:
        async with self._uow:
            run = await self._backup_repository.get_run(data)
        if run.status != BackupRunStatus.COMPLETED or not run.file_path:
            raise NotFoundError("Backup not ready", code=ErrorCode.BACKUP_NOT_READY)
        path = Path(run.file_path)
        if not path.exists():
            raise NotFoundError("Backup file missing", code=ErrorCode.BACKUP_FILE_MISSING)
        return path
