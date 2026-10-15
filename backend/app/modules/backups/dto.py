from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Optional

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import BackupKind, BackupRunStatus


class BackupSettingsDto(BaseDto, TimestampMixin):
    enabled: bool
    interval_hours: int
    max_files: int


@dataclass(frozen=True, kw_only=True)
class UpdateBackupSettingsDto:
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = None
    max_files: Optional[int] = None


class BackupRunDto(BaseDto, TimestampMixin):
    id: int
    kind: BackupKind
    status: BackupRunStatus
    file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum_sha256: Optional[str] = None
    triggered_by: Optional[int] = None
    error: Optional[str] = None
    finished_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class CreateBackupRunDto:
    kind: BackupKind
    triggered_by: Optional[int] = None


class BackupStatsDto(BaseDto):
    completed_count: int = 0
    failed_count: int = 0
    total_size_bytes: int = 0
    last_database_backup: Optional[BackupRunDto] = None
    next_run_at: Optional[datetime] = None


@dataclass(frozen=True, kw_only=True)
class ListBackupRunsDto:
    kind: Optional[BackupKind] = None
    status: Optional[BackupRunStatus] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class RunBackupDto:
    kind: BackupKind
    run_id: int


@dataclass(frozen=True, kw_only=True)
class StartBackupRunDto:
    kind: BackupKind


# a run older than this was stranded by a killed worker; a real dump finishes well within it
STALE_RUN_AFTER: Final[timedelta] = timedelta(hours=2)
