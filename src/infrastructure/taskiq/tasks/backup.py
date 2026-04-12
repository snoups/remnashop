from dishka.integrations.taskiq import FromDishka, inject

from src.application.use_cases.backup.commands import AutoBackupDatabase
from src.infrastructure.taskiq.broker import broker


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def auto_backup_task(auto_backup: FromDishka[AutoBackupDatabase]) -> None:
    await auto_backup.system()
