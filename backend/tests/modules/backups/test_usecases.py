from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus, Locale, Role
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.modules.backups.dto import (
    BackupRunDto,
    BackupSettingsDto,
    CreateBackupRunDto,
    ListBackupRunsDto,
    UpdateBackupSettingsDto,
)
from app.modules.backups.repository import BackupRepository
from app.modules.backups.usecases.create_backup_run import CreateBackupRunUseCase
from app.modules.backups.usecases.delete_backup_run import DeleteBackupRunUseCase
from app.modules.backups.usecases.get_backup_run import GetBackupRunUseCase
from app.modules.backups.usecases.get_backup_settings import GetBackupSettingsUseCase
from app.modules.backups.usecases.get_backup_stats import (
    GetBackupStatsUseCase,
    next_scheduled_run,
)
from app.modules.backups.usecases.list_backup_runs import ListBackupRunsUseCase
from app.modules.backups.usecases.reset_backup_settings import ResetBackupSettingsUseCase
from app.modules.backups.usecases.update_backup_settings import UpdateBackupSettingsUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN_NO_GRANT = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    # triggered_by is a real FK, so unlike OWNER this actor needs a row
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    return user


async def test_owner_can_get_settings(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GetBackupSettingsUseCase(backup_repository, uow)
    settings = await use_case(OWNER)
    assert settings.enabled is False


async def test_admin_without_grant_cannot_get_settings(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GetBackupSettingsUseCase(backup_repository, uow)
    with pytest.raises(PermissionDeniedError):
        await use_case(ADMIN_NO_GRANT)


async def test_owner_can_update_settings(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateBackupSettingsUseCase(backup_repository, uow)
    result = await use_case(OWNER, UpdateBackupSettingsDto(enabled=True, interval_hours=6))
    assert result.enabled is True
    assert result.interval_hours == 6


async def test_owner_can_reset_settings(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    await UpdateBackupSettingsUseCase(backup_repository, uow)(
        OWNER, UpdateBackupSettingsDto(enabled=True, interval_hours=6)
    )
    result = await ResetBackupSettingsUseCase(backup_repository, uow)(OWNER)
    assert result.enabled is False
    assert result.interval_hours == 24


async def test_admin_without_grant_cannot_reset_settings(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    use_case = ResetBackupSettingsUseCase(backup_repository, uow)
    with pytest.raises(PermissionDeniedError):
        await use_case(ADMIN_NO_GRANT)


async def test_create_backup_run_enqueues_task(
    backup_repository: BackupRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    dispatch = RecordingDispatch()
    use_case = CreateBackupRunUseCase(backup_repository, uow, dispatch)
    run = await use_case(owner, BackupKind.DATABASE)
    assert run.status.name == "PENDING"
    assert dispatch.messages == [{"kind": "DATABASE", "run_id": run.id}]


async def test_create_backup_run_rejects_when_already_running(
    backup_repository: BackupRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    dispatch = RecordingDispatch()
    use_case = CreateBackupRunUseCase(backup_repository, uow, dispatch)
    await use_case(owner, BackupKind.DATABASE)
    async with uow:
        runs, _ = await backup_repository.list_runs(kind=BackupKind.DATABASE)
        await backup_repository.mark_running(runs[0].id)

    with pytest.raises(ConflictError):
        await use_case(owner, BackupKind.DATABASE)


async def test_list_backup_runs_returns_page(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListBackupRunsUseCase(backup_repository, uow)
    runs, total = await use_case(OWNER, ListBackupRunsDto())
    assert total == 0
    assert runs == []


async def test_get_backup_run_returns_row(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    use_case = GetBackupRunUseCase(backup_repository, uow)
    fetched = await use_case(OWNER, created.id)
    assert fetched.id == created.id


async def test_delete_backup_run_removes_it(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    use_case = DeleteBackupRunUseCase(backup_repository, uow)
    await use_case(OWNER, created.id)
    with pytest.raises(NotFoundError):
        await backup_repository.get_run(created.id)


async def test_delete_backup_run_does_not_unlink_file_when_commit_fails(
    backup_repository: BackupRepository, uow: UnitOfWork, tmp_path
) -> None:
    dump_file = tmp_path / "db.dump"
    dump_file.write_bytes(b"x")
    async with uow:
        created = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(created.id)
        await backup_repository.mark_completed(
            created.id, file_path=str(dump_file), size_bytes=1, checksum_sha256="a" * 64
        )

    use_case = DeleteBackupRunUseCase(backup_repository, uow)
    # the row delete flushes, the commit fails: the file is unlinked only after
    # a clean commit, so it must survive
    with patch.object(uow, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))):
        with pytest.raises(RuntimeError):
            await use_case(OWNER, created.id)

    assert dump_file.exists()


async def test_owner_can_get_stats(backup_repository: BackupRepository, uow: UnitOfWork) -> None:
    stats = await GetBackupStatsUseCase(backup_repository, uow)(OWNER)
    assert stats.completed_count == 0
    assert stats.next_run_at is None  # scheduling is off by default


async def test_admin_without_grant_cannot_get_stats(
    backup_repository: BackupRepository, uow: UnitOfWork
) -> None:
    with pytest.raises(PermissionDeniedError):
        await GetBackupStatsUseCase(backup_repository, uow)(ADMIN_NO_GRANT)


_NOW = datetime(2026, 9, 25, 10, 48, tzinfo=timezone.utc)


def _settings(*, enabled: bool, interval_hours: int = 24) -> BackupSettingsDto:
    return BackupSettingsDto(enabled=enabled, interval_hours=interval_hours, max_files=7)


def _finished(at: datetime) -> BackupRunDto:
    return BackupRunDto(
        id=1, kind=BackupKind.DATABASE, status=BackupRunStatus.COMPLETED, finished_at=at
    )


@pytest.mark.parametrize(
    ("settings", "latest", "expected"),
    [
        (_settings(enabled=False), None, None),
        (_settings(enabled=True), None, datetime(2026, 9, 25, 11, tzinfo=timezone.utc)),
        (
            _settings(enabled=True, interval_hours=24),
            _finished(datetime(2026, 9, 25, 3, 0, 12, tzinfo=timezone.utc)),
            datetime(2026, 9, 26, 4, tzinfo=timezone.utc),
        ),
        (
            _settings(enabled=True, interval_hours=6),
            _finished(_NOW - timedelta(hours=30)),
            datetime(2026, 9, 25, 11, tzinfo=timezone.utc),
        ),
        (
            _settings(enabled=True, interval_hours=2),
            _finished(datetime(2026, 9, 25, 10, tzinfo=timezone.utc)),
            datetime(2026, 9, 25, 12, tzinfo=timezone.utc),
        ),
    ],
)
def test_next_scheduled_run_lands_on_the_first_due_hourly_tick(
    settings: BackupSettingsDto, latest: Optional[BackupRunDto], expected: Optional[datetime]
) -> None:
    assert next_scheduled_run(settings, latest, _NOW) == expected
