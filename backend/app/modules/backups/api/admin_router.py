from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.enums import BackupKind, BackupRunStatus
from app.modules.backups.api.schemas import (
    BackupRunPageResponse,
    BackupRunResponse,
    BackupSettingsResponse,
    BackupStatsResponse,
    CreateBackupRunRequest,
    UpdateBackupSettingsRequest,
)
from app.modules.backups.dto import ListBackupRunsDto, StartBackupRunDto, UpdateBackupSettingsDto
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

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("/settings", response_model=BackupSettingsResponse)
@inject
async def get_backup_settings(
    use_case: FromDishka[GetBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor)
    return BackupSettingsResponse.model_validate(settings, from_attributes=True)


@router.patch("/settings", response_model=BackupSettingsResponse)
@inject
async def update_backup_settings(
    body: UpdateBackupSettingsRequest,
    use_case: FromDishka[UpdateBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(
        actor,
        UpdateBackupSettingsDto(
            enabled=body.enabled,
            interval_hours=body.interval_hours,
            max_files=body.max_files,
        ),
    )
    return BackupSettingsResponse.model_validate(settings, from_attributes=True)


@router.post("/settings/actions/reset", response_model=BackupSettingsResponse)
@inject
async def reset_backup_settings(
    use_case: FromDishka[ResetBackupSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupSettingsResponse:
    settings = await use_case(actor)
    return BackupSettingsResponse.model_validate(settings, from_attributes=True)


@router.get("/summary", response_model=BackupStatsResponse)
@inject
async def get_backup_summary(
    use_case: FromDishka[GetBackupStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupStatsResponse:
    stats = await use_case(actor)
    return BackupStatsResponse.model_validate(stats, from_attributes=True)


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
    run = await use_case(actor, StartBackupRunDto(kind=body.kind))
    return BackupRunResponse.model_validate(run, from_attributes=True)


@router.get("/runs", response_model=BackupRunPageResponse)
@inject
async def list_backup_runs(
    use_case: FromDishka[ListBackupRunsUseCase],
    actor: Actor = Depends(require_admin),
    kind: Optional[BackupKind] = Query(default=None),
    status_filter: Optional[BackupRunStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> BackupRunPageResponse:
    runs, total = await use_case(
        actor, ListBackupRunsDto(kind=kind, status=status_filter, page=page, page_size=page_size)
    )
    return BackupRunPageResponse(
        items=[BackupRunResponse.model_validate(r, from_attributes=True) for r in runs],
        total=total,
    )


@router.get("/runs/{run_id:int}", response_model=BackupRunResponse, responses=error_responses(404))
@inject
async def get_backup_run(
    run_id: int,
    use_case: FromDishka[GetBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> BackupRunResponse:
    run = await use_case(actor, run_id)
    return BackupRunResponse.model_validate(run, from_attributes=True)


@router.get("/runs/{run_id:int}/download", responses=error_responses(404))
@inject
async def download_backup_run(
    run_id: int,
    use_case: FromDishka[DownloadBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> FileResponse:
    path = await use_case(actor, run_id)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.delete(
    "/runs/{run_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_backup_run(
    run_id: int,
    use_case: FromDishka[DeleteBackupRunUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, run_id)
