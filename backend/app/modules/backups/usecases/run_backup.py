import asyncio
import contextlib
import hashlib
import os
from collections.abc import Awaitable
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import DATETIME_FILE_FORMAT
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups.cancel_signal import cancel_signal_key
from app.modules.backups.dto import STALE_RUN_AFTER, RunBackupDto
from app.modules.backups.dump import (
    BACKUP_FILE_MODE,
    create_assets_dump,
    create_signed_database_dump,
)
from app.modules.backups.events import BackupCompletedEvent, BackupFailedEvent
from app.modules.backups.repository import BackupRepository

_STALE_RUN_ERROR: Final[str] = "Interrupted: the worker stopped before the backup finished"
_CANCEL_POLL_S: Final[float] = 1.0
_EXTENSION_BY_KIND: Final[dict[BackupKind, str]] = {
    BackupKind.DATABASE: "dump",
    BackupKind.ASSETS: "zip",
}


class RunBackupUseCase(UseCase[RunBackupDto, None]):
    required_permission = None

    def __init__(
        self,
        backup_repository: BackupRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
        redis: Redis,
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher
        self._redis = redis

    async def _is_canceled_while(self, run_id: int, work: Awaitable[Any]) -> bool:
        task = asyncio.ensure_future(work)
        key = cancel_signal_key(run_id)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=_CANCEL_POLL_S)
                if done:
                    await task
                    return False
                if await self._redis.exists(key):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    await self._redis.delete(key)
                    return True
        finally:
            task.cancel()

    async def _fail_stranded(self, kind: BackupKind, run_id: int, started_after: datetime) -> None:
        async with self._uow:
            stale = await self._backup_repository.fail_stale(
                kind, before=started_after, error=_STALE_RUN_ERROR, exclude_run_id=run_id
            )
            for stale_id in stale:
                await self._event_publisher.publish(
                    BackupFailedEvent(run_id=stale_id, kind=kind, error=_STALE_RUN_ERROR)
                )
        for stale_id in stale:
            logger.warning(f"Backup run '{stale_id}' ('{kind.value}') was stranded, failed it")

    async def _execute(self, actor: Actor, data: RunBackupDto) -> None:
        kind, run_id = data.kind, data.run_id
        started_after = datetime_now() - STALE_RUN_AFTER
        await self._fail_stranded(kind, run_id, started_after)

        async with self._uow:
            await self._backup_repository.lock_kind(kind)
            # a redelivered message for a run that already ran must leave it as it is
            run = await self._backup_repository.get_run(run_id)
            pending = run.status is BackupRunStatus.PENDING
            # only a run that already started blocks this one; queued siblings take turns
            busy = pending and await self._backup_repository.has_active(
                kind, started_after=started_after, exclude_run_id=run_id, pending=False
            )
            started = pending and not busy and await self._backup_repository.mark_running(run_id)
        if busy:
            error = f"A '{kind.value}' backup is already running"
            async with self._uow:
                await self._backup_repository.mark_failed(run_id, error=error)
                await self._event_publisher.publish(
                    BackupFailedEvent(run_id=run_id, kind=kind, error=error)
                )
            logger.warning(f"Backup run '{run_id}' rejected: '{kind.value}' already running")
            return
        if not started:
            logger.info(f"Backup run '{run_id}' is no longer pending, skipped")
            return

        backup_dir = self._config.media_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
        # run_id suffix: two runs in the same second (second-precision
        # DATETIME_FILE_FORMAT) would share a filename, and rotation would then
        # unlink it out from under the surviving run
        stem = f"{kind.value}_{timestamp}_{run_id}"
        dest: Optional[Path] = None

        try:
            if kind is BackupKind.DATABASE:
                dest = backup_dir / f"{stem}.{_EXTENSION_BY_KIND[kind]}"
                work: Awaitable[Any] = create_signed_database_dump(self._config, dest)
            else:
                dest = backup_dir / f"{stem}.{_EXTENSION_BY_KIND[kind]}"
                work = create_assets_dump(self._config, backup_dir / stem)

            if await self._is_canceled_while(run_id, work):
                dest.unlink(missing_ok=True)
                async with self._uow:
                    await self._backup_repository.mark_canceled(run_id)
                logger.info(f"Backup run '{run_id}' ('{kind.value}') canceled")
                return

            if kind is BackupKind.ASSETS:
                os.chmod(dest, BACKUP_FILE_MODE)

            with dest.open("rb") as f:
                checksum = hashlib.file_digest(f, "sha256").hexdigest()
            size_bytes = dest.stat().st_size

            async with self._uow:
                await self._backup_repository.mark_completed(
                    run_id, file_path=str(dest), size_bytes=size_bytes, checksum_sha256=checksum
                )
                await self._event_publisher.publish(
                    BackupCompletedEvent(run_id=run_id, kind=kind, size_bytes=size_bytes)
                )
            logger.info(f"Backup run '{run_id}' ('{kind.value}') completed: {dest}")

        except Exception as exc:
            logger.exception(f"Backup run '{run_id}' ('{kind.value}') failed")
            if dest is not None:
                dest.unlink(missing_ok=True)
            async with self._uow:
                await self._backup_repository.mark_failed(run_id, error=str(exc))
                await self._event_publisher.publish(
                    BackupFailedEvent(run_id=run_id, kind=kind, error=str(exc))
                )
            return

        try:
            await self._rotate(kind)
        except Exception:
            logger.exception(f"Backup run '{run_id}' ('{kind.value}') rotation failed")

    async def _rotate(self, kind: BackupKind) -> None:
        async with self._uow:
            completed = await self._backup_repository.list_completed_for_rotation(kind)
            settings = await self._backup_repository.get_settings()
        for stale in completed[settings.max_files :]:
            if stale.file_path:
                Path(stale.file_path).unlink(missing_ok=True)
            async with self._uow:
                await self._backup_repository.delete_run(stale.id)
