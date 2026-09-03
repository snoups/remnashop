from dataclasses import dataclass
from datetime import datetime
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import BackupKind, BackupRunStatus

DEFAULT_PAGE_SIZE: Final[int] = 50


class BackupSettingsDto(BaseDto, TimestampMixin):
    id: int = 1
    enabled: bool = False
    interval_hours: int = 24
    max_files: int = 7


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
