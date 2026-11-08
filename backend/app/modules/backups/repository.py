from datetime import datetime
from typing import Final, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.db.models.backup_run import BackupRun
from app.core.db.models.backup_settings import BackupSettings
from app.core.db.partial_update import apply_partial_update
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.core.enums import BackupKind, BackupRunStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.backups.dto import (
    BackupRunDto,
    BackupSettingsDto,
    CreateBackupRunDto,
    UpdateBackupSettingsDto,
)

# one key per backup kind, so two worker runs of one kind decide one at a time
_BACKUP_KIND_LOCK_KEY: Final[int] = 8221942


class BackupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_settings_dto(self, row: BackupSettings) -> BackupSettingsDto:
        return BackupSettingsDto.model_validate(row, from_attributes=True)

    def _to_run_dto(self, row: BackupRun) -> BackupRunDto:
        return BackupRunDto.model_validate(row, from_attributes=True)

    async def get_settings(self) -> BackupSettingsDto:
        row = await get_or_create_singleton(self.session, BackupSettings, SINGLETON_ID)
        return self._to_settings_dto(row)

    async def update_settings(self, data: UpdateBackupSettingsDto) -> BackupSettingsDto:
        row = await get_or_create_singleton(self.session, BackupSettings, SINGLETON_ID)
        apply_partial_update(row, data)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_settings_dto(row)

    async def reset_settings(self) -> BackupSettingsDto:
        # the row is recreated from the model's defaults
        await self.session.execute(delete(BackupSettings))
        return await self.get_settings()

    async def _get_row(self, run_id: int) -> BackupRun:
        row = await self.session.get(BackupRun, run_id)
        if row is None:
            raise NotFoundError(
                f"Backup run '{run_id}' not found", code=ErrorCode.BACKUP_RUN_NOT_FOUND
            )
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

    async def lock_kind(self, kind: BackupKind) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(_BACKUP_KIND_LOCK_KEY, list(BackupKind).index(kind)))
        )

    async def has_active(
        self,
        kind: BackupKind,
        *,
        started_after: datetime,
        exclude_run_id: Optional[int] = None,
        pending: bool = True,
    ) -> bool:
        # a click counts PENDING too, so a second click can't pass before the
        # worker starts; the worker counts only RUNNING, under lock_kind(), so
        # queued siblings take turns. Older rows were stranded by a killed worker.
        statuses = (
            (BackupRunStatus.PENDING, BackupRunStatus.RUNNING)
            if pending
            else (BackupRunStatus.RUNNING,)
        )
        conditions = [
            BackupRun.kind == kind,
            BackupRun.status.in_(statuses),
            BackupRun.updated_at >= started_after,
        ]
        if exclude_run_id is not None:
            conditions.append(BackupRun.id != exclude_run_id)
        stmt = select(func.count()).select_from(BackupRun).where(*conditions)
        count = await self.session.scalar(stmt)
        return bool(count)

    async def fail_stale(
        self, kind: BackupKind, *, before: datetime, error: str, exclude_run_id: int
    ) -> list[int]:
        rows = await self.session.scalars(
            update(BackupRun)
            .where(
                BackupRun.kind == kind,
                BackupRun.status.in_((BackupRunStatus.PENDING, BackupRunStatus.RUNNING)),
                BackupRun.updated_at < before,
                BackupRun.id != exclude_run_id,
            )
            .values(status=BackupRunStatus.FAILED, error=error, finished_at=datetime_now())
            .returning(BackupRun.id)
            .execution_options(synchronize_session=False)
        )
        return list(rows)

    async def mark_running(self, run_id: int) -> bool:
        # a redelivered message for a finished run must not start it again
        row = await self._get_row(run_id)
        if row.status is not BackupRunStatus.PENDING:
            return False
        row.status = BackupRunStatus.RUNNING
        await self.session.flush()
        return True

    async def mark_completed(
        self, run_id: int, *, file_path: str, size_bytes: int, checksum_sha256: str
    ) -> BackupRunDto:
        row = await self._get_row(run_id)
        row.status = BackupRunStatus.COMPLETED
        row.file_path = file_path
        row.size_bytes = size_bytes
        row.checksum_sha256 = checksum_sha256
        row.error = None
        row.finished_at = datetime_now()
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_run_dto(row)

    async def cancel_if_pending(self, run_id: int) -> bool:
        return await self._cancel(run_id, BackupRunStatus.PENDING)

    async def mark_canceled(self, run_id: int) -> bool:
        return await self._cancel(run_id, BackupRunStatus.RUNNING)

    async def _cancel(self, run_id: int, expected: BackupRunStatus) -> bool:
        canceled = await self.session.scalar(
            update(BackupRun)
            .where(BackupRun.id == run_id, BackupRun.status == expected)
            .values(status=BackupRunStatus.CANCELED, finished_at=datetime_now())
            .returning(BackupRun.id)
            .execution_options(synchronize_session=False)
        )
        await self.session.flush()
        self.session.expire_all()
        return canceled is not None

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
        # created_at is transaction-time `now()`, so runs from one transaction
        # tie; id breaks the tie
        stmt = (
            select(BackupRun)
            .where(BackupRun.kind == kind, BackupRun.status == BackupRunStatus.COMPLETED)
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_run_dto(r) for r in rows]

    async def find_latest_completed(self, kind: BackupKind) -> Optional[BackupRunDto]:
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
