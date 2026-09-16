from unittest.mock import AsyncMock, patch

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, Locale, Role
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.modules.backups.dto import CreateBackupRunDto, UpdateBackupSettingsDto
from app.modules.backups.repository import BackupRepository
from app.modules.backups.usecases.create_backup_run import CreateBackupRunUseCase
from app.modules.backups.usecases.delete_backup_run import DeleteBackupRunUseCase
from app.modules.backups.usecases.get_backup_run import GetBackupRunUseCase
from app.modules.backups.usecases.get_backup_settings import GetBackupSettingsUseCase
from app.modules.backups.usecases.list_backup_runs import ListBackupRunsInput, ListBackupRunsUseCase
from app.modules.backups.usecases.update_backup_settings import UpdateBackupSettingsUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN_NO_GRANT = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    # CreateBackupRunUseCase persists triggered_by, which has a real FK to
    # users.id -- unlike OWNER above, this actor must exist in the DB.
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


class _FakeTaskDispatch:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def kiq(self, **kwargs) -> None:
        self.calls.append(kwargs)


async def test_create_backup_run_enqueues_task(
    backup_repository: BackupRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    dispatch = _FakeTaskDispatch()
    use_case = CreateBackupRunUseCase(backup_repository, uow, dispatch)
    run = await use_case(owner, BackupKind.DATABASE)
    assert run.status.name == "PENDING"
    assert dispatch.calls == [{"kind": "DATABASE", "run_id": run.id}]


async def test_create_backup_run_rejects_when_already_running(
    backup_repository: BackupRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    dispatch = _FakeTaskDispatch()
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
    runs, total = await use_case(OWNER, ListBackupRunsInput())
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
    # simulate a mid-transaction failure: the row delete flushes fine, but the
    # commit itself blows up -- the old buggy code unlinked the file BEFORE even
    # touching the DB, so it would have removed it here regardless; the fix only
    # unlinks after `async with self._uow:` exits cleanly, so a failed commit
    # must leave the file untouched
    with patch.object(uow, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))):
        with pytest.raises(RuntimeError):
            await use_case(OWNER, created.id)

    assert dump_file.exists()
