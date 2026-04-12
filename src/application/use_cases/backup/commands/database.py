import shutil
import tempfile
from pathlib import Path

from loguru import logger

from src.application.common import Interactor, Notifier
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.dto import MediaDescriptorDto, MessagePayloadDto, UserDto
from src.core.constants import BACKUP_DIR, DATETIME_FILE_FORMAT
from src.core.enums import MediaType, Role
from src.core.utils.time import datetime_now

from .dump import CreateDatabaseDump


class AutoBackupDatabase(Interactor[None, None]):
    required_permission = None

    def __init__(
        self,
        settings_dao: SettingsDao,
        notifier: Notifier,
        create_database_dump: CreateDatabaseDump,
    ) -> None:
        self.settings_dao = settings_dao
        self.notifier = notifier
        self.create_database_dump = create_database_dump

    async def _execute(self, actor: UserDto, data: None) -> None:
        settings = await self.settings_dao.get()
        backup_cfg = settings.backup

        if not backup_cfg.enabled:
            return

        BACKUP_DIR.mkdir(exist_ok=True)
        existing = sorted(BACKUP_DIR.glob("db_backup_*.sql"), key=lambda f: f.stat().st_mtime)

        if existing:
            elapsed_hours = (datetime_now().timestamp() - existing[-1].stat().st_mtime) / 3600
            if elapsed_hours < backup_cfg.interval_hours:
                return

        timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
        tmp_dir = Path(tempfile.mkdtemp())

        try:
            dump_file = tmp_dir / f"db_backup_{timestamp}.sql"
            await self.create_database_dump.system(dump_file)

            self._rotate(existing, backup_cfg.max_files)

            final_path = BACKUP_DIR / dump_file.name
            shutil.copy2(dump_file, final_path)
            logger.info(f"Auto backup created: {final_path.name}")

            if backup_cfg.send_to_chat:
                try:
                    await self.notifier.notify_admins(
                        payload=MessagePayloadDto(
                            i18n_key="",
                            media=MediaDescriptorDto(
                                kind="fs",
                                value=str(final_path),
                                filename=final_path.name,
                            ),
                            media_type=MediaType.DOCUMENT,
                            delete_after=None,
                            disable_default_markup=True,
                        ),
                        roles=[Role.OWNER, Role.DEV],
                    )
                except Exception as e:
                    logger.warning(f"Failed to send backup to admins: {e}")

        except Exception as e:
            logger.exception(f"Auto backup failed: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _rotate(files: list[Path], max_files: int) -> None:
        while len(files) >= max_files:
            files.pop(0).unlink(missing_ok=True)


class BackupDatabase(Interactor[None, None]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, notifier: Notifier, create_database_dump: CreateDatabaseDump) -> None:
        self.notifier = notifier
        self.create_database_dump = create_database_dump

    async def _execute(self, actor: UserDto, data: None) -> None:
        await self.notifier.notify_user(actor, i18n_key="ntf-backup.db-started")

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
            dump_file = tmp_dir / f"db_backup_{timestamp}.sql"

            await self.create_database_dump.system(dump_file)

            await self.notifier.notify_user(
                user=actor,
                payload=MessagePayloadDto(
                    i18n_key="",
                    media=MediaDescriptorDto(
                        kind="fs",
                        value=str(dump_file),
                        filename=dump_file.name,
                    ),
                    media_type=MediaType.DOCUMENT,
                    delete_after=None,
                    disable_default_markup=False,
                ),
            )
            logger.info(f"{actor.log} Database backup sent: {dump_file.name}")
        except Exception as e:
            logger.exception(f"{actor.log} Failed to create database backup: {e}")
            await self.notifier.notify_user(actor, i18n_key="ntf-backup.error")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
