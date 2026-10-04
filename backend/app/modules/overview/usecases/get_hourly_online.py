from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import TIMEZONE
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.dto import HourlyOnlineDto, HourlyOnlinePointDto
from app.modules.overview.online import read_hourly_online_peaks, read_latest_online

_HOURS: Final[int] = 24


class GetHourlyOnlineUseCase(UseCase[None, HourlyOnlineDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _execute(self, actor: Actor, data: None) -> HourlyOnlineDto:
        current_hour = (
            datetime_now().astimezone(TIMEZONE).replace(minute=0, second=0, microsecond=0)
        )
        hours = [current_hour - timedelta(hours=h) for h in range(_HOURS - 1, -1, -1)]
        peaks = await read_hourly_online_peaks(self._redis, hours)
        return HourlyOnlineDto(
            current=await read_latest_online(self._redis),
            points=[HourlyOnlinePointDto(hour=h, peak=p) for h, p in zip(hours, peaks)],
        )
