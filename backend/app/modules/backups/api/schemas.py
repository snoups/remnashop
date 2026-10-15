from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import BackupKind, BackupRunStatus


class BackupSettingsResponse(BaseModel):
    enabled: bool
    interval_hours: int
    max_files: int


class UpdateBackupSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = Field(default=None, ge=1, le=8760)
    max_files: Optional[int] = Field(default=None, ge=1, le=365)


class CreateBackupRunRequest(BaseModel):
    kind: BackupKind


class BackupRunResponse(BaseModel):
    id: int
    kind: BackupKind
    status: BackupRunStatus
    size_bytes: Optional[int] = None
    checksum_sha256: Optional[str] = None
    triggered_by: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class BackupRunPageResponse(BaseModel):
    items: list[BackupRunResponse]
    total: int


class BackupStatsResponse(BaseModel):
    completed_count: int
    failed_count: int
    total_size_bytes: int
    last_database_backup: Optional[BackupRunResponse] = None
    next_run_at: Optional[datetime] = None
