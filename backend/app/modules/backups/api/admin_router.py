from pathlib import Path
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import BackupKind, BackupRunStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.backups.api.schemas import (
    BackupRunPageResponse,
    BackupRunResponse,
    BackupSettingsResponse,
    BackupStatsResponse,
    CreateBackupRunRequest,
    UpdateBackupSettingsRequest,
)
from app.modules.backups.dto import (
    DEFAULT_PAGE_SIZE,
    BackupRunDto,
    BackupSettingsDto,
    UpdateBackupSettingsDto,
)
from app.modules.backups.usecases import (
    CreateBackupRunUseCase,
    DeleteBackupRunUseCase,
    DownloadBackupRunUseCase,
    GetBackupRunUseCase,
    GetBackupSettingsUseCase,
    GetBackupStatsUseCase,
    ListBackupRunsInput,
    ListBackupRunsUseCase,
    ResetBackupSettingsUseCase,
    UpdateBackupSettingsUseCase,
)

router = APIRouter(prefix="/backups", tags=["backups"])


def _to_settings_response(settings: BackupSettingsDto) -> BackupSettingsResponse:
    return BackupSettingsResponse(
        enabled=settings.enabled,
        interval_hours=settings.interval_hours,
        max_files=settings.max_files,
    )


def _to_run_response(run: BackupRunDto) -> BackupRunResponse:
    return BackupRunResponse(
        id=run.id,
        kind=run.kind,
        status=run.status,
        size_bytes=run.size_bytes,
        checksum_sha256=run.checksum_sha256,
        triggered_by=run.triggered_by,
        error=run.error,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


@router.get("/settings", response_model=BackupSettingsResponse)
@inject
async def get_backup_settings(
    use_case: FromDishka[GetBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor)
    return _to_settings_response(settings)


@router.patch("/settings", response_model=BackupSettingsResponse)
@inject
async def update_backup_settings(
    body: UpdateBackupSettingsRequest,
    use_case: FromDishka[UpdateBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor, UpdateBackupSettingsDto(**body.model_dump()))
    return _to_settings_response(settings)


@router.post("/settings/actions/reset", response_model=BackupSettingsResponse)
@inject
async def reset_backup_settings(
    use_case: FromDishka[ResetBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor)
    return _to_settings_response(settings)


@router.get("/stats", response_model=BackupStatsResponse)
@inject
async def get_backup_stats(
    use_case: FromDishka[GetBackupStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupStatsResponse:
    stats = await use_case(actor)
    latest = stats.last_database_backup
    return BackupStatsResponse(
        completed_count=stats.completed_count,
        failed_count=stats.failed_count,
        total_size_bytes=stats.total_size_bytes,
        last_database_backup=_to_run_response(latest) if latest is not None else None,
        next_run_at=stats.next_run_at,
    )


@router.post(
    "/runs",
    response_model=BackupRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(409),
)
@inject
async def create_backup_run(
    body: CreateBackupRunRequest,
    use_case: FromDishka[CreateBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupRunResponse:
    run = await use_case(actor, body.kind)
    return _to_run_response(run)


@router.get("/runs", response_model=BackupRunPageResponse)
@inject
async def list_backup_runs(
    use_case: FromDishka[ListBackupRunsUseCase],
    actor: Actor = Depends(require_admin),
    kind: Optional[BackupKind] = Query(default=None),
    status_filter: Optional[BackupRunStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=200),
) -> BackupRunPageResponse:
    runs, total = await use_case(
        actor, ListBackupRunsInput(kind=kind, status=status_filter, page=page, page_size=page_size)
    )
    return BackupRunPageResponse(
        items=[_to_run_response(r) for r in runs], total=total, page=page, page_size=page_size
    )


@router.get("/runs/{run_id}", response_model=BackupRunResponse, responses=error_responses(404))
@inject
async def get_backup_run(
    run_id: int,
    use_case: FromDishka[GetBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupRunResponse:
    run = await use_case(actor, run_id)
    return _to_run_response(run)


@router.get("/runs/{run_id}/download", responses=error_responses(404))
@inject
async def download_backup_run(
    run_id: int,
    use_case: FromDishka[DownloadBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> FileResponse:
    run = await use_case(actor, run_id)
    if run.status != BackupRunStatus.COMPLETED or not run.file_path:
        raise NotFoundError("Backup not ready", code=ErrorCode.BACKUP_NOT_READY)
    path = Path(run.file_path)
    if not path.exists():
        raise NotFoundError("Backup file missing", code=ErrorCode.BACKUP_FILE_MISSING)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.delete(
    "/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_backup_run(
    run_id: int,
    use_case: FromDishka[DeleteBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, run_id)
