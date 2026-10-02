from dishka.integrations.taskiq import FromDishka, inject

from app.modules.overview.usecases import SampleRemnawaveOnlineUseCase
from app.worker.broker import broker


@broker.task(schedule=[{"cron": "*/5 * * * *"}])
@inject(patch_module=True)
async def sample_remnawave_online_task(use_case: FromDishka[SampleRemnawaveOnlineUseCase]) -> None:
    await use_case.system()
