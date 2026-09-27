from typing import Final, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.backup_run import BackupRun
from app.core.db.models.backup_settings import BackupSettings
from app.core.enums import BackupKind, BackupRunStatus
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.backups.dto import (
    DEFAULT_PAGE_SIZE,
    BackupRunDto,
    BackupSettingsDto,
    CreateBackupRunDto,
    UpdateBackupSettingsDto,
)

_SINGLETON_ID: Final[int] = 1


class BackupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_settings_dto(self, row: Optional[BackupSettings]) -> BackupSettingsDto:
        if row is None:
            return BackupSettingsDto()
        return BackupSettingsDto(
            id=row.id,
            enabled=row.enabled,
            interval_hours=row.interval_hours,
            max_files=row.max_files,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_run_dto(self, row: BackupRun) -> BackupRunDto:
        return BackupRunDto(
            id=row.id,
            kind=row.kind,
            status=row.status,
            file_path=row.file_path,
            size_bytes=row.size_bytes,
            checksum_sha256=row.checksum_sha256,
            triggered_by=row.triggered_by,
            error=row.error,
            finished_at=row.finished_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_settings(self) -> BackupSettingsDto:
        row = await self.session.get(BackupSettings, _SINGLETON_ID)
        return self._to_settings_dto(row)

    async def update_settings(self, data: UpdateBackupSettingsDto) -> BackupSettingsDto:
        row = await self.session.get(BackupSettings, _SINGLETON_ID)
        if row is None:
            row = BackupSettings(id=_SINGLETON_ID)
            self.session.add(row)

        if data.enabled is not None:
            row.enabled = data.enabled
        if data.interval_hours is not None:
            row.interval_hours = data.interval_hours
        if data.max_files is not None:
            row.max_files = data.max_files

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_settings_dto(row)

    async def _get_row(self, run_id: int) -> BackupRun:
        row = await self.session.get(BackupRun, run_id)
        if row is None:
            raise NotFoundError(f"Backup run '{run_id}' not found")
        return row

    async def get_run(self, run_id: int) -> BackupRunDto:
        return self._to_run_dto(await self._get_row(run_id))

    async def create_run(self, data: CreateBackupRunDto) -> BackupRunDto:
        row = BackupRun(
            kind=data.kind, status=BackupRunStatus.PENDING, triggered_by=data.triggered_by
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_run_dto(row)

    async def has_active(self, kind: BackupKind, *, exclude_run_id: Optional[int] = None) -> bool:
        # PENDING counts too -- a just-created run sits there until the
        # worker picks it up, and a second click in that window must not
        # slip past a guard that only looks for RUNNING. exclude_run_id lets
        # run_backup() ask "is some OTHER run active" without matching its
        # own still-PENDING row.
        conditions = [
            BackupRun.kind == kind,
            BackupRun.status.in_((BackupRunStatus.PENDING, BackupRunStatus.RUNNING)),
        ]
        if exclude_run_id is not None:
            conditions.append(BackupRun.id != exclude_run_id)
        stmt = select(func.count()).select_from(BackupRun).where(*conditions)
        count = await self.session.scalar(stmt)
        return bool(count)

    async def mark_running(self, run_id: int) -> BackupRunDto:
        row = await self._get_row(run_id)
        row.status = BackupRunStatus.RUNNING
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_run_dto(row)

    async def mark_completed(
        self, run_id: int, *, file_path: str, size_bytes: int, checksum_sha256: str
    ) -> BackupRunDto:
        row = await self._get_row(run_id)
        row.status = BackupRunStatus.COMPLETED
        row.file_path = file_path
        row.size_bytes = size_bytes
        row.checksum_sha256 = checksum_sha256
        row.finished_at = datetime_now()
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_run_dto(row)

    async def mark_failed(self, run_id: int, *, error: str) -> BackupRunDto:
        row = await self._get_row(run_id)
        row.status = BackupRunStatus.FAILED
        row.error = error
        row.finished_at = datetime_now()
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_run_dto(row)

    async def list_runs(
        self,
        *,
        kind: Optional[BackupKind] = None,
        status: Optional[BackupRunStatus] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[BackupRunDto], int]:
        filters = []
        if kind is not None:
            filters.append(BackupRun.kind == kind)
        if status is not None:
            filters.append(BackupRun.status == status)

        total = await self.session.scalar(
            select(func.count()).select_from(BackupRun).where(*filters)
        )
        stmt = (
            select(BackupRun)
            .where(*filters)
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_run_dto(r) for r in rows], int(total or 0)

    async def list_completed_for_rotation(self, kind: BackupKind) -> list[BackupRunDto]:
        # created_at is Postgres transaction-time `now()` -- ties within one
        # transaction (e.g. two runs completed back-to-back) need id as a
        # stable secondary sort for "newest first" to actually hold.
        stmt = (
            select(BackupRun)
            .where(BackupRun.kind == kind, BackupRun.status == BackupRunStatus.COMPLETED)
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_run_dto(r) for r in rows]

    async def get_latest_completed(self, kind: BackupKind) -> Optional[BackupRunDto]:
        stmt = (
            select(BackupRun)
            .where(BackupRun.kind == kind, BackupRun.status == BackupRunStatus.COMPLETED)
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
            .limit(1)
        )
        row = await self.session.scalar(stmt)
        return self._to_run_dto(row) if row is not None else None

    async def count_by_status(self) -> tuple[int, int, int]:
        completed = BackupRun.status == BackupRunStatus.COMPLETED
        stmt = select(
            func.count().filter(completed),
            func.count().filter(BackupRun.status == BackupRunStatus.FAILED),
            func.coalesce(func.sum(BackupRun.size_bytes).filter(completed), 0),
        )
        completed_count, failed_count, total_size = (await self.session.execute(stmt)).one()
        return int(completed_count), int(failed_count), int(total_size)

    async def delete_run(self, run_id: int) -> None:
        row = await self._get_row(run_id)
        await self.session.delete(row)
        await self.session.flush()
