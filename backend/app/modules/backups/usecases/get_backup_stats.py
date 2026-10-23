from datetime import datetime, timedelta
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups.dto import BackupRunDto, BackupSettingsDto, BackupStatsDto
from app.modules.backups.repository import BackupRepository


def next_scheduled_run(
    settings: BackupSettingsDto, latest: Optional[BackupRunDto], now: datetime
) -> Optional[datetime]:
    # mirrors tasks.auto_backup: an hourly cron tick fires once the interval
    # since the last completed database backup has elapsed
    if not settings.enabled:
        return None
    due = now
    if latest is not None and latest.finished_at is not None:
        due = max(now, latest.finished_at + timedelta(hours=settings.interval_hours))
    tick = due.replace(minute=0, second=0, microsecond=0)
    return tick if tick == due else tick + timedelta(hours=1)


class GetBackupStatsUseCase(UseCase[None, BackupStatsDto]):
    required_permission = Permission.BACKUPS_STATS_VIEW

    def __init__(self, backup_repository: BackupRepository, uow: UnitOfWork) -> None:
        self._backup_repository = backup_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> BackupStatsDto:
        async with self._uow:
            settings = await self._backup_repository.get_settings()
            latest = await self._backup_repository.find_latest_completed(BackupKind.DATABASE)
            completed, failed, total_size = await self._backup_repository.count_by_status()
        return BackupStatsDto(
            completed_count=completed,
            failed_count=failed,
            total_size_bytes=total_size,
            last_database_backup=latest,
            next_run_at=next_scheduled_run(settings, latest, datetime_now()),
        )
