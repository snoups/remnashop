import hashlib
import os
from pathlib import Path
from typing import Final, Optional

from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import DATETIME_FILE_FORMAT
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups.dto import RunBackupDto
from app.modules.backups.dump import create_assets_dump, create_database_dump
from app.modules.backups.events import BackupFailedEvent
from app.modules.backups.provenance import sign_backup_file
from app.modules.backups.repository import BackupRepository

_FILE_MODE: Final[int] = 0o600
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
    ) -> None:
        self._backup_repository = backup_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: RunBackupDto) -> None:
        kind, run_id = data.kind, data.run_id
        if await self._backup_repository.has_active(kind, exclude_run_id=run_id):
            async with self._uow:
                await self._backup_repository.mark_failed(
                    run_id, error=f"A '{kind.value}' backup is already running"
                )
            logger.warning(f"Backup run '{run_id}' rejected: '{kind.value}' already running")
            return

        async with self._uow:
            await self._backup_repository.mark_running(run_id)

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
                await create_database_dump(self._config, dest)
                os.chmod(dest, _FILE_MODE)
                sign_backup_file(dest, self._config.crypt_key.get_secret_value())
            else:
                dest = await create_assets_dump(self._config, backup_dir / stem)
                os.chmod(dest, _FILE_MODE)

            with dest.open("rb") as f:
                checksum = hashlib.file_digest(f, "sha256").hexdigest()
            size_bytes = dest.stat().st_size

            async with self._uow:
                await self._backup_repository.mark_completed(
                    run_id, file_path=str(dest), size_bytes=size_bytes, checksum_sha256=checksum
                )
            logger.info(f"Backup run '{run_id}' ('{kind.value}') completed: {dest}")

        except Exception as exc:
            logger.exception(f"Backup run '{run_id}' ('{kind.value}') failed")
            if dest is not None:
                dest.unlink(missing_ok=True)
            async with self._uow:
                await self._backup_repository.mark_failed(run_id, error=str(exc))
                await self._event_publisher.publish(
                    BackupFailedEvent(run_id=run_id, kind=kind.value, error=str(exc))
                )
            return

        try:
            await self._rotate(kind)
        except Exception:
            logger.exception(f"Backup run '{run_id}' ('{kind.value}') rotation failed")

    async def _rotate(self, kind: BackupKind) -> None:
        completed = await self._backup_repository.list_completed_for_rotation(kind)
        settings = await self._backup_repository.get_settings()
        for stale in completed[settings.max_files :]:
            if stale.file_path:
                Path(stale.file_path).unlink(missing_ok=True)
            async with self._uow:
                await self._backup_repository.delete_run(stale.id)
