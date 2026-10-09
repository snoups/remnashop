import hashlib
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update

from app.core.actor import Actor
from app.core.db.models.backup_run import BackupRun
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus
from app.core.utils.time import datetime_now
from app.modules.backups.dto import CreateBackupRunDto, RunBackupDto, UpdateBackupSettingsDto
from app.modules.backups.dump import create_assets_dump
from app.modules.backups.repository import BackupRepository
from app.modules.backups.usecases import RunBackupUseCase, RunScheduledBackupUseCase


async def test_run_backup_marks_failed_when_dump_raises(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    tmp_path: Path,
    config,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    with patch(
        "app.modules.backups.usecases.run_backup.create_database_dump",
        AsyncMock(side_effect=RuntimeError("pg_dump failed: boom")),
    ):
        await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )

    failed = await backup_repository.get_run(run.id)
    assert failed.status == BackupRunStatus.FAILED
    assert "boom" in (failed.error or "")

    published = (
        await backup_repository.session.scalars(
            select(EventOutboxEntry).where(EventOutboxEntry.event_type == "BackupFailedEvent")
        )
    ).all()
    assert len(published) == 1
    assert published[0].payload["run_id"] == run.id


async def test_run_backup_rejects_second_concurrent_run(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    async with uow:
        first = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(first.id)
        second = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
        RunBackupDto(kind=BackupKind.DATABASE, run_id=second.id)
    )

    failed = await backup_repository.get_run(second.id)
    assert failed.status == BackupRunStatus.FAILED
    assert "already running" in (failed.error or "")


async def test_run_backup_completes_and_signs_database_dump(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    dump_bytes = b"fake pg_dump bytes"

    async def _fake_dump(cfg, dest: Path) -> None:
        dest.write_bytes(dump_bytes)

    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    with patch("app.modules.backups.usecases.run_backup.create_database_dump", _fake_dump):
        await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )

    completed = await backup_repository.get_run(run.id)
    assert completed.status == BackupRunStatus.COMPLETED
    assert completed.file_path is not None
    written = Path(completed.file_path).read_bytes()
    assert written.startswith(dump_bytes)  # provenance trailer appended after
    assert completed.checksum_sha256 == hashlib.sha256(written).hexdigest()


async def test_run_backup_completes_assets_dump(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    (tmp_path / "logo.png").write_bytes(b"img")

    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))

    await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
        RunBackupDto(kind=BackupKind.ASSETS, run_id=run.id)
    )

    completed = await backup_repository.get_run(run.id)
    assert completed.status == BackupRunStatus.COMPLETED
    assert completed.file_path is not None
    assert completed.file_path.endswith(".zip")
    assert Path(completed.file_path).exists()


async def test_run_backup_removes_partial_file_on_failure(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)

    async def _fake_dump(cfg, dest: Path) -> None:
        dest.write_bytes(b"partial")
        raise RuntimeError("pg_dump failed mid-write")

    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    with patch("app.modules.backups.usecases.run_backup.create_database_dump", _fake_dump):
        await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )

    assert (await backup_repository.get_run(run.id)).status == BackupRunStatus.FAILED
    assert list((tmp_path / "backups").glob("DATABASE_*")) == []


async def test_run_backup_rotates_old_files_beyond_max_files(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    async with uow:
        await backup_repository.update_settings(UpdateBackupSettingsDto(max_files=1))

    async def _fake_dump(cfg, dest: Path) -> None:
        dest.write_bytes(b"x")

    with patch("app.modules.backups.usecases.run_backup.create_database_dump", _fake_dump):
        for _ in range(2):
            async with uow:
                run = await backup_repository.create_run(
                    CreateBackupRunDto(kind=BackupKind.DATABASE)
                )
            await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
                RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
            )

    remaining, total = await backup_repository.list_runs(
        kind=BackupKind.DATABASE, status=BackupRunStatus.COMPLETED
    )
    assert total == 1
    assert len(list((tmp_path / "backups").glob("DATABASE_*.dump"))) == 1


async def test_create_assets_dump_excludes_backups_subdir(config, tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    (media_dir / "sub").mkdir(parents=True)
    (media_dir / "sub" / "keep.txt").write_bytes(b"keep me")
    (media_dir / "backups").mkdir()
    (media_dir / "backups" / "DATABASE_secret.dump").write_bytes(b"db dump content")

    config.media_dir = media_dir
    result = await create_assets_dump(config, media_dir / "backups" / "assets_run")

    assert result.exists()
    with zipfile.ZipFile(result) as zf:
        names = zf.namelist()
    assert any(n.endswith("media/sub/keep.txt") for n in names)
    assert not any("backups" in n for n in names)


async def test_create_assets_dump_builds_temp_file_inside_backups_dir(
    config, tmp_path: Path
) -> None:
    # the temp zip MUST be created inside backups_dir, not the system temp dir --
    # media/ is a separate volume in every real deployment, and os.replace()
    # across devices raises EXDEV. Asserting the dir= kwarg passed to mkstemp
    # is what actually guarantees the final os.replace() stays same-device.
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    config.media_dir = media_dir
    backups_dir = media_dir / "backups"

    real_mkstemp = tempfile.mkstemp
    seen_dirs = []

    def spy_mkstemp(*args, **kwargs):
        seen_dirs.append(kwargs.get("dir"))
        return real_mkstemp(*args, **kwargs)

    with patch("app.modules.backups.dump.tempfile.mkstemp", side_effect=spy_mkstemp):
        result = await create_assets_dump(config, backups_dir / "assets_run")

    assert seen_dirs == [backups_dir]
    assert result.parent == backups_dir


class _RecordingRunBackup(RunBackupUseCase):
    def __init__(self) -> None:
        self.runs: list[RunBackupDto] = []

    async def _execute(self, actor: Actor, data: RunBackupDto) -> None:
        self.runs.append(data)


async def test_auto_backup_noops_when_disabled(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    run_backup = _RecordingRunBackup()

    await RunScheduledBackupUseCase(backup_repository, uow, run_backup).system()

    assert run_backup.runs == []


async def test_auto_backup_runs_when_no_prior_run(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    async with uow:
        await backup_repository.update_settings(
            UpdateBackupSettingsDto(enabled=True, interval_hours=24)
        )

    run_backup = _RecordingRunBackup()

    await RunScheduledBackupUseCase(backup_repository, uow, run_backup).system()

    assert [run.kind for run in run_backup.runs] == [BackupKind.DATABASE]


async def _complete_run_at(
    backup_repository: BackupRepository, uow: UnitOfWork, finished_at
) -> None:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(run.id)
        await backup_repository.mark_completed(
            run.id, file_path=f"/x/{run.id}.dump", size_bytes=1, checksum_sha256="a" * 64
        )
        row = await backup_repository._get_row(run.id)
        row.finished_at = finished_at


async def test_auto_backup_runs_when_last_run_older_than_interval(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    async with uow:
        await backup_repository.update_settings(
            UpdateBackupSettingsDto(enabled=True, interval_hours=6)
        )
    await _complete_run_at(backup_repository, uow, datetime_now() - timedelta(hours=7))

    run_backup = _RecordingRunBackup()

    await RunScheduledBackupUseCase(backup_repository, uow, run_backup).system()

    assert len(run_backup.runs) == 1


async def test_auto_backup_noops_when_last_run_younger_than_interval(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    async with uow:
        await backup_repository.update_settings(
            UpdateBackupSettingsDto(enabled=True, interval_hours=6)
        )
    await _complete_run_at(backup_repository, uow, datetime_now() - timedelta(hours=1))

    run_backup = _RecordingRunBackup()

    await RunScheduledBackupUseCase(backup_repository, uow, run_backup).system()

    assert run_backup.runs == []


async def _failed_events(backup_repository: BackupRepository) -> list[int]:
    rows = await backup_repository.session.scalars(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type == "BackupFailedEvent")
    )
    return [row.payload["run_id"] for row in rows]


async def _running_since(
    backup_repository: BackupRepository, uow: UnitOfWork, age: timedelta
) -> int:
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.mark_running(run.id)
        await backup_repository.session.execute(
            update(BackupRun)
            .where(BackupRun.id == run.id)
            .values(created_at=datetime_now() - age, updated_at=datetime_now() - age)
        )
    return run.id


async def test_run_backup_fails_a_run_stranded_by_a_killed_worker(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    stranded = await _running_since(backup_repository, uow, timedelta(hours=3))
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    with patch(
        "app.modules.backups.usecases.run_backup.create_database_dump",
        AsyncMock(side_effect=lambda config, dest: dest.write_bytes(b"dump")),
    ):
        await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )

    assert (await backup_repository.get_run(stranded)).status == BackupRunStatus.FAILED
    assert (await backup_repository.get_run(run.id)).status == BackupRunStatus.COMPLETED
    assert await _failed_events(backup_repository) == [stranded]


async def test_run_backup_still_waits_for_a_long_running_backup(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    running = await _running_since(backup_repository, uow, timedelta(minutes=90))
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
        RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
    )

    assert (await backup_repository.get_run(running)).status == BackupRunStatus.RUNNING
    assert (await backup_repository.get_run(run.id)).status == BackupRunStatus.FAILED
    assert await _failed_events(backup_repository) == [run.id]


async def test_run_backup_does_not_fail_itself_after_a_long_queue(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher,
) -> None:
    monkeypatch.setattr(config, "media_dir", tmp_path)
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        old = datetime_now() - timedelta(hours=3)
        await backup_repository.session.execute(
            update(BackupRun).where(BackupRun.id == run.id).values(created_at=old, updated_at=old)
        )

    with patch(
        "app.modules.backups.usecases.run_backup.create_database_dump",
        AsyncMock(side_effect=lambda config, dest: dest.write_bytes(b"dump")),
    ):
        await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
            RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
        )

    done = await backup_repository.get_run(run.id)
    assert done.status == BackupRunStatus.COMPLETED and done.error is None
    assert await _failed_events(backup_repository) == []


async def test_run_backup_keeps_a_run_that_started_late_after_queueing(
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config,
    event_publisher,
) -> None:
    async with uow:
        queued = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
        await backup_repository.session.execute(
            update(BackupRun)
            .where(BackupRun.id == queued.id)
            .values(created_at=datetime_now() - timedelta(hours=3))
        )
        await backup_repository.mark_running(queued.id)
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    await RunBackupUseCase(backup_repository, uow, config, event_publisher).system(
        RunBackupDto(kind=BackupKind.DATABASE, run_id=run.id)
    )

    assert (await backup_repository.get_run(queued.id)).status == BackupRunStatus.RUNNING
    assert (await backup_repository.get_run(run.id)).status == BackupRunStatus.FAILED
