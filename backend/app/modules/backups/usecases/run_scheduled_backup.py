from datetime import timedelta

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups.dto import CreateBackupRunDto, RunBackupDto
from app.modules.backups.repository import BackupRepository
from app.modules.backups.usecases.run_backup import RunBackupUseCase


class RunScheduledBackupUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        backup_repository: BackupRepository,
        uow: UnitOfWork,
        run_backup_use_case: RunBackupUseCase,
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._run_backup_use_case = run_backup_use_case

    async def _execute(self, actor: Actor, data: None) -> None:
        settings = await self._backup_repository.get_settings()
        if not settings.enabled:
            return

        latest = await self._backup_repository.get_latest_completed(BackupKind.DATABASE)
        if latest is not None and latest.finished_at is not None:
            if datetime_now() - latest.finished_at < timedelta(hours=settings.interval_hours):
                return

        # triggered_by=None (create_run's default) marks a scheduler-started run
        async with self._uow:
            run = await self._backup_repository.create_run(
                CreateBackupRunDto(kind=BackupKind.DATABASE)
            )

        await self._run_backup_use_case.system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )
