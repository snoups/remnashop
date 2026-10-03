from pathlib import Path

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.repository import BackupRepository


class DeleteBackupRunUseCase(UseCase[int, None]):
    required_permission = Permission.BACKUPS_RUN_DELETE

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            run = await self._backup_repository.get_run(data)
        async with self._uow:
            await self._backup_repository.delete_run(data)
        # unlink only after the delete commits, so a rollback keeps the file
        if run.file_path:
            Path(run.file_path).unlink(missing_ok=True)
        logger.info(f"Backup run '{data}' deleted by actor {actor.log}")
