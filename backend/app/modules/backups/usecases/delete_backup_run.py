from pathlib import Path

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.repository import BackupRepository
from app.modules.users import UserDto


class DeleteBackupRunUseCase(UseCase[int, None]):
    required_permission = Permission.BACKUPS_RUN_DELETE

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        run = await self._backup_repository.get_run(data)
        async with self._uow:
            await self._backup_repository.delete_run(data)
        # unlink only after the row deletion has committed -- a rolled-back
        # transaction must never leave the file already gone
        if run.file_path:
            Path(run.file_path).unlink(missing_ok=True)
        logger.info(f"Backup run '{data}' deleted by actor {actor.log}")
