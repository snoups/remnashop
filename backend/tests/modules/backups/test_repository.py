import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus
from app.core.exceptions import NotFoundError
from app.modules.backups.dto import CreateBackupRunDto, UpdateBackupSettingsDto
from app.modules.backups.repository import BackupRepository


async def test_get_settings_returns_defaults_before_any_write(
    backup_repository: BackupRepository,
) -> None:
    settings = await backup_repository.get_settings()
    assert settings.enabled is False
    assert settings.interval_hours == 24
    assert settings.max_files == 7


async def test_update_settings_persists_partial_update(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        updated = await backup_repository.update_settings(
            UpdateBackupSettingsDto(enabled=True, max_files=3)
        )
    assert updated.enabled is True
    assert updated.max_files == 3
    assert updated.interval_hours == 24  # untouched field keeps its default


async def test_reset_settings_restores_defaults(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await backup_repository.update_settings(
            UpdateBackupSettingsDto(enabled=True, interval_hours=6, max_files=3)
        )
        reset = await backup_repository.reset_settings()
    assert (reset.enabled, reset.interval_hours, reset.max_files) == (False, 24, 7)
    settings = await backup_repository.get_settings()
    assert (settings.enabled, settings.interval_hours, settings.max_files) == (False, 24, 7)


async def test_create_run_starts_pending(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    assert run.status == BackupRunStatus.PENDING
    assert run.kind == BackupKind.DATABASE


async def test_has_active_counts_pending_and_running(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    # PENDING counts: a second click before the worker starts must not pass
    assert await backup_repository.has_active(BackupKind.DATABASE) is True
    assert await backup_repository.has_active(BackupKind.ASSETS) is False

    async with uow:
        await backup_repository.mark_running(run.id)
    assert await backup_repository.has_active(BackupKind.DATABASE) is True


async def test_has_active_excludes_its_own_run_id(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    # run_backup() passes its own PENDING row, which must not match itself
    assert await backup_repository.has_active(BackupKind.DATABASE, exclude_run_id=run.id) is False

    async with uow:
        other = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    assert await backup_repository.has_active(BackupKind.DATABASE, exclude_run_id=run.id) is True
    assert await backup_repository.has_active(BackupKind.DATABASE, exclude_run_id=other.id) is True


async def test_mark_completed_sets_terminal_fields(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(run.id)
        completed = await backup_repository.mark_completed(
            run.id, file_path="/x/db.dump", size_bytes=123, checksum_sha256="a" * 64
        )
    assert completed.status == BackupRunStatus.COMPLETED
    assert completed.size_bytes == 123
    assert completed.finished_at is not None


async def test_mark_failed_records_error(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        failed = await backup_repository.mark_failed(run.id, error="pg_dump exited 1")
    assert failed.status == BackupRunStatus.FAILED
    assert failed.error == "pg_dump exited 1"


async def test_list_runs_filters_by_kind_and_paginates(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        for _ in range(3):
            await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))

    runs, total = await backup_repository.list_runs(kind=BackupKind.DATABASE, page=1, page_size=2)
    assert total == 3
    assert len(runs) == 2
    assert all(r.kind == BackupKind.DATABASE for r in runs)


async def test_list_runs_filters_by_status(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        pending = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(run.id)
        completed = await backup_repository.mark_completed(
            run.id, file_path="/x/db.dump", size_bytes=1, checksum_sha256="a" * 64
        )

    runs, total = await backup_repository.list_runs(
        kind=BackupKind.DATABASE, status=BackupRunStatus.COMPLETED
    )
    assert total == 1
    assert [r.id for r in runs] == [completed.id]
    assert pending.id not in [r.id for r in runs]


async def test_list_completed_for_rotation_orders_newest_first(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    ids = []
    async with uow:
        for _ in range(2):
            run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
            await backup_repository.mark_running(run.id)
            completed = await backup_repository.mark_completed(
                run.id, file_path=f"/x/{run.id}.dump", size_bytes=1, checksum_sha256="a" * 64
            )
            ids.append(completed.id)

    ordered = await backup_repository.list_completed_for_rotation(BackupKind.DATABASE)
    assert [r.id for r in ordered] == list(reversed(ids))


async def test_delete_run_removes_row(backup_repository: BackupRepository, uow: UnitOfWork) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.delete_run(run.id)

    with pytest.raises(NotFoundError):
        await backup_repository.get_run(run.id)


async def test_count_by_status_sums_only_completed_sizes(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        for size in (100, 250):
            run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
            await backup_repository.mark_completed(
                run.id, file_path=f"/x/{size}.dump", size_bytes=size, checksum_sha256="a" * 64
            )
        failed = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))
        await backup_repository.mark_failed(failed.id, error="boom")
        await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))

    assert await backup_repository.count_by_status() == (2, 1, 350)
