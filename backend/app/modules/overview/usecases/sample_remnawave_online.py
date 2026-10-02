from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.online import record_online_sample


class SampleRemnawaveOnlineUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, remnawave_sdk: RemnawaveSDK, redis: Redis) -> None:
        self._remnawave_sdk = remnawave_sdk
        self._redis = redis

    async def _execute(self, actor: Actor, data: None) -> None:
        stats = await self._remnawave_sdk.system.get_stats()
        await record_online_sample(
            self._redis, datetime_now().date(), int(stats.online_stats.online_now)
        )
