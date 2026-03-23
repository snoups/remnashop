import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.dao import SettingsDao, UserDao
from src.application.dto import MediaDescriptorDto, MessagePayloadDto
from src.core.config import AppConfig
from src.core.constants import BASE_DIR
from src.core.enums import MediaType, Role
from src.infrastructure.taskiq.broker import broker

BACKUP_DIR = BASE_DIR / "backups"


def _rotate_backups(max_files: int) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    files = sorted(BACKUP_DIR.glob("db_backup_*.sql"), key=lambda f: f.stat().st_mtime)
    while len(files) >= max_files:
        files.pop(0).unlink(missing_ok=True)


async def _run_pg_dump(dump_file: Path, config: AppConfig) -> None:
    db = config.database
    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h", db.host,
        "-p", str(db.port),
        "-U", db.user,
        "-d", db.name,
        "-f", str(dump_file),
        env={**__import__("os").environ, "PGPASSWORD": db.password.get_secret_value()},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {stderr.decode()}")


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def auto_backup_task(
    settings_dao: FromDishka[SettingsDao],
    user_dao: FromDishka[UserDao],
    notifier: FromDishka[Notifier],
    config: FromDishka[AppConfig],
) -> None:
    settings = await settings_dao.get()
    backup_cfg = settings.backup

    if not backup_cfg.enabled:
        return

    # Проверяем нужно ли запускать по интервалу
    BACKUP_DIR.mkdir(exist_ok=True)
    files = sorted(BACKUP_DIR.glob("db_backup_*.sql"), key=lambda f: f.stat().st_mtime)
    if files:
        last_mtime = files[-1].stat().st_mtime
        elapsed_hours = (datetime.now().timestamp() - last_mtime) / 3600
        if elapsed_hours < backup_cfg.interval_hours:
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir = Path(tempfile.mkdtemp())

    try:
        dump_file = tmp_dir / f"db_backup_{timestamp}.sql"
        await _run_pg_dump(dump_file, config)

        _rotate_backups(backup_cfg.max_files)

        final_path = BACKUP_DIR / dump_file.name
        shutil.copy2(dump_file, final_path)
        logger.info(f"Auto backup created: {final_path.name}")

        if backup_cfg.send_to_chat:
            owners = await user_dao.filter_by_role([Role.OWNER, Role.DEV])
            for owner in owners:
                try:
                    await notifier.notify_user(
                        user=owner,
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
                    )
                except Exception as e:
                    logger.warning(f"Failed to send backup to owner '{owner.telegram_id}': {e}")

    except Exception as e:
        logger.exception(f"Auto backup failed: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
