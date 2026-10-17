from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.broker import broker
from app.core.enums import BackupKind
from app.core.utils.lock import cron_lock
from app.modules.backups.dto import RunBackupDto
from app.modules.backups.usecases import RunBackupUseCase, RunScheduledBackupUseCase

_AUTO_BACKUP_LOCK_TTL_S: Final[int] = 55 * 60  # under the hourly cron interval


@broker.task
@inject(patch_module=True)
async def run_backup_task(kind: str, run_id: int, use_case: FromDishka[RunBackupUseCase]) -> None:
    await use_case.system(RunBackupDto(kind=BackupKind(kind), run_id=run_id))


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def auto_backup_task(
    use_case: FromDishka[RunScheduledBackupUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(redis, "auto_backup", ttl_seconds=_AUTO_BACKUP_LOCK_TTL_S) as acquired:
        if not acquired:
            logger.debug("auto_backup_task already running, skipping this tick")
            return
        await use_case.system()
