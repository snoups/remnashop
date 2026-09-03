from pathlib import Path
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies.admin import require_admin
from app.core.enums import BackupKind, BackupRunStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.backups.api.schemas import (
    BackupRunPageResponse,
    BackupRunResponse,
    BackupSettingsResponse,
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
    ListBackupRunsInput,
    ListBackupRunsUseCase,
    UpdateBackupSettingsUseCase,
)
from app.modules.users import UserDto

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
async def get_settings(
    use_case: FromDishka[GetBackupSettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor)
    return _to_settings_response(settings)


@router.put("/settings", response_model=BackupSettingsResponse)
@inject
async def update_settings(
    body: UpdateBackupSettingsRequest,
    use_case: FromDishka[UpdateBackupSettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor, UpdateBackupSettingsDto(**body.model_dump()))
    return _to_settings_response(settings)


@router.post("/runs", response_model=BackupRunResponse, status_code=status.HTTP_202_ACCEPTED)
@inject
async def create_run(
    body: CreateBackupRunRequest,
    use_case: FromDishka[CreateBackupRunUseCase],
    actor: UserDto = Depends(require_admin),
) -> BackupRunResponse:
    try:
        run = await use_case(actor, body.kind)
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_run_response(run)


@router.get("/runs", response_model=BackupRunPageResponse)
@inject
async def list_runs(
    use_case: FromDishka[ListBackupRunsUseCase],
    actor: UserDto = Depends(require_admin),
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


@router.get("/runs/{run_id}", response_model=BackupRunResponse)
@inject
async def get_run(
    run_id: int,
    use_case: FromDishka[GetBackupRunUseCase],
    actor: UserDto = Depends(require_admin),
) -> BackupRunResponse:
    try:
        run = await use_case(actor, run_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_run_response(run)


@router.get("/runs/{run_id}/download")
@inject
async def download_run(
    run_id: int,
    use_case: FromDishka[DownloadBackupRunUseCase],
    actor: UserDto = Depends(require_admin),
) -> FileResponse:
    try:
        run = await use_case(actor, run_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if run.status != BackupRunStatus.COMPLETED or not run.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not ready")
    path = Path(run.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file missing")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_run(
    run_id: int,
    use_case: FromDishka[DeleteBackupRunUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, run_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
