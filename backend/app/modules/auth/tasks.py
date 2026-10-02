from dishka.integrations.taskiq import FromDishka, inject

from app.modules.auth.usecases import PruneStaleSessionsUseCase
from app.worker.broker import broker


@broker.task(schedule=[{"cron": "45 3 * * *"}])
@inject(patch_module=True)
async def prune_stale_sessions_task(use_case: FromDishka[PruneStaleSessionsUseCase]) -> None:
    await use_case.system()
