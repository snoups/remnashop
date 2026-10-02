from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.backups.dto import BackupRunDto, ListBackupRunsDto
from app.modules.backups.repository import BackupRepository


class ListBackupRunsUseCase(UseCase[ListBackupRunsDto, tuple[list[BackupRunDto], int]]):
    required_permission = Permission.BACKUPS_VIEW

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListBackupRunsDto
    ) -> tuple[list[BackupRunDto], int]:
        async with self._uow:
            return await self._backup_repository.list_runs(
                kind=data.kind, status=data.status, page=data.page, page_size=data.page_size
            )
