from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.remnawave_online import record_online_sample
from app.core.utils.time import datetime_now
from app.worker.broker import broker


@broker.task(schedule=[{"cron": "*/5 * * * *"}])
@inject(patch_module=True)
async def sample_remnawave_online_task(
    remnawave_sdk: FromDishka[RemnawaveSDK], redis: FromDishka[Redis]
) -> None:
    stats = await remnawave_sdk.system.get_stats()
    await record_online_sample(redis, datetime_now().date(), int(stats.online_stats.online_now))
