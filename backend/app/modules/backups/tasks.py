import hashlib
import os
from datetime import timedelta
from pathlib import Path
from typing import Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import DATETIME_FILE_FORMAT
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.backups.dto import CreateBackupRunDto
from app.modules.backups.dump import create_assets_dump, create_database_dump
from app.modules.backups.provenance import sign_backup_file
from app.modules.backups.repository import BackupRepository
from app.worker.broker import broker

_FILE_MODE: Final[int] = 0o600
_EXTENSION_BY_KIND: Final[dict[BackupKind, str]] = {
    BackupKind.DATABASE: "dump",
    BackupKind.ASSETS: "zip",
}


async def run_backup(
    *,
    kind: BackupKind,
    run_id: int,
    backup_repository: BackupRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    if await backup_repository.has_running(kind):
        async with uow:
            await backup_repository.mark_failed(
                run_id, error=f"A '{kind.value}' backup is already running"
            )
        logger.warning(f"Backup run '{run_id}' rejected: '{kind.value}' already running")
        return

    async with uow:
        await backup_repository.mark_running(run_id)

    backup_dir = config.media_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
    # run_id suffix guards against two runs landing in the same second
    # (second-precision DATETIME_FILE_FORMAT) and colliding on one filename --
    # a real collision, not just theoretical: rotation would then unlink the
    # shared path out from under the surviving run.
    stem = f"{kind.value}_{timestamp}_{run_id}"
    ext = _EXTENSION_BY_KIND[kind]
    dest: Optional[Path] = None

    try:
        if kind is BackupKind.DATABASE:
            dest = backup_dir / f"{stem}.{ext}"
            await create_database_dump(config, dest)
            os.chmod(dest, _FILE_MODE)
            sign_backup_file(dest, config.crypt_key.get_secret_value())
        else:
            dest = await create_assets_dump(config, backup_dir / stem)
            os.chmod(dest, _FILE_MODE)

        with dest.open("rb") as f:
            checksum = hashlib.file_digest(f, "sha256").hexdigest()
        size_bytes = dest.stat().st_size

        async with uow:
            await backup_repository.mark_completed(
                run_id, file_path=str(dest), size_bytes=size_bytes, checksum_sha256=checksum
            )
        logger.info(f"Backup run '{run_id}' ('{kind.value}') completed: {dest}")

    except Exception as exc:
        logger.exception(f"Backup run '{run_id}' ('{kind.value}') failed")
        if dest is not None:
            dest.unlink(missing_ok=True)
        async with uow:
            await backup_repository.mark_failed(run_id, error=str(exc))
        return

    try:
        await _rotate(backup_repository, uow, kind)
    except Exception:
        logger.exception(f"Backup run '{run_id}' ('{kind.value}') rotation failed")


async def _rotate(backup_repository: BackupRepository, uow: UnitOfWork, kind: BackupKind) -> None:
    completed = await backup_repository.list_completed_for_rotation(kind)
    settings = await backup_repository.get_settings()
    for stale in completed[settings.max_files :]:
        if stale.file_path:
            Path(stale.file_path).unlink(missing_ok=True)
        async with uow:
            await backup_repository.delete_run(stale.id)


@broker.task
@inject(patch_module=True)
async def run_backup_task(
    kind: str,
    run_id: int,
    backup_repository: FromDishka[BackupRepository],
    uow: FromDishka[UnitOfWork],
    config: FromDishka[AppConfig],
) -> None:
    await run_backup(
        kind=BackupKind(kind),
        run_id=run_id,
        backup_repository=backup_repository,
        uow=uow,
        config=config,
    )


_AUTO_BACKUP_LOCK_TTL_S: Final[int] = 55 * 60  # under the hourly cron interval


async def auto_backup(
    *, backup_repository: BackupRepository, uow: UnitOfWork, config: AppConfig
) -> None:
    settings = await backup_repository.get_settings()
    if not settings.enabled:
        return

    latest = await backup_repository.get_latest_completed(BackupKind.DATABASE)
    if latest is not None and latest.finished_at is not None:
        elapsed = datetime_now() - latest.finished_at
        if elapsed < timedelta(hours=settings.interval_hours):
            return

    # triggered_by=None (create_run's default) is what marks this run as
    # scheduler-started rather than admin-triggered -- see BackupRun.triggered_by.
    async with uow:
        run = await backup_repository.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))

    await run_backup(
        kind=BackupKind.DATABASE,
        run_id=run.id,
        backup_repository=backup_repository,
        uow=uow,
        config=config,
    )


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def auto_backup_task(
    backup_repository: FromDishka[BackupRepository],
    uow: FromDishka[UnitOfWork],
    config: FromDishka[AppConfig],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(redis, "auto_backup", ttl_seconds=_AUTO_BACKUP_LOCK_TTL_S) as acquired:
        if not acquired:
            logger.debug("auto_backup_task already running, skipping this tick")
            return
        await auto_backup(backup_repository=backup_repository, uow=uow, config=config)
