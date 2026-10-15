from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.backups.dispatch import RunBackupDispatch
from app.modules.backups.repository import BackupRepository
from app.modules.backups.tasks import run_backup_task
from app.modules.backups.usecases import (
    CreateBackupRunUseCase,
    DeleteBackupRunUseCase,
    DownloadBackupRunUseCase,
    GetBackupRunUseCase,
    GetBackupSettingsUseCase,
    GetBackupStatsUseCase,
    ListBackupRunsUseCase,
    ResetBackupSettingsUseCase,
    RunBackupUseCase,
    RunScheduledBackupUseCase,
    UpdateBackupSettingsUseCase,
)


class BackupsProvider(Provider):
    scope = Scope.REQUEST

    backup_repository = provide(BackupRepository)
    use_cases = provide_all(
        GetBackupSettingsUseCase,
        GetBackupStatsUseCase,
        UpdateBackupSettingsUseCase,
        ResetBackupSettingsUseCase,
        CreateBackupRunUseCase,
        ListBackupRunsUseCase,
        GetBackupRunUseCase,
        DownloadBackupRunUseCase,
        DeleteBackupRunUseCase,
        RunBackupUseCase,
        RunScheduledBackupUseCase,
    )

    @provide(scope=Scope.APP)
    def run_backup_dispatch(self) -> RunBackupDispatch:
        return cast(RunBackupDispatch, run_backup_task)


def get_backups_providers() -> list[Provider]:
    return [BackupsProvider()]
