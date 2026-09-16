from typing import Protocol

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind
from app.core.exceptions import ConflictError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupRunDto, CreateBackupRunDto
from app.modules.backups.repository import BackupRepository
from app.modules.users import UserDto


class RunBackupDispatch(Protocol):
    async def kiq(self, *, kind: str, run_id: int) -> object: ...


class CreateBackupRunUseCase(UseCase[BackupKind, BackupRunDto]):
    required_permission = Permission.BACKUPS_RUN_CREATE

    def __init__(
        self,
        backup_repository: BackupRepository,
        uow: UnitOfWork,
        run_backup_dispatch: RunBackupDispatch,
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._run_backup_dispatch = run_backup_dispatch

    async def _execute(self, actor: UserDto, data: BackupKind) -> BackupRunDto:
        async with self._uow:
            if await self._backup_repository.has_active(data):
                raise ConflictError(f"A '{data.value}' backup is already running")

        async with self._uow:
            run = await self._backup_repository.create_run(
                CreateBackupRunDto(kind=data, triggered_by=actor.id)
            )

        await self._run_backup_dispatch.kiq(kind=data.value, run_id=run.id)
        logger.info(f"Backup run '{run.id}' ('{data.value}') enqueued by actor {actor.log}")
        return run
