from dishka import Provider, Scope, provide

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
    UpdateBackupSettingsUseCase,
)
from app.modules.backups.usecases.create_backup_run import RunBackupDispatch


class BackupsProvider(Provider):
    scope = Scope.REQUEST

    backup_repository = provide(BackupRepository)
    get_backup_settings_use_case = provide(GetBackupSettingsUseCase)
    get_backup_stats_use_case = provide(GetBackupStatsUseCase)
    update_backup_settings_use_case = provide(UpdateBackupSettingsUseCase)
    reset_backup_settings_use_case = provide(ResetBackupSettingsUseCase)
    create_backup_run_use_case = provide(CreateBackupRunUseCase)
    list_backup_runs_use_case = provide(ListBackupRunsUseCase)
    get_backup_run_use_case = provide(GetBackupRunUseCase)
    download_backup_run_use_case = provide(DownloadBackupRunUseCase)
    delete_backup_run_use_case = provide(DeleteBackupRunUseCase)

    @provide
    def run_backup_dispatch(self) -> RunBackupDispatch:
        return run_backup_task  # type: ignore[return-value]


def get_backups_providers() -> list[Provider]:
    return [BackupsProvider()]
