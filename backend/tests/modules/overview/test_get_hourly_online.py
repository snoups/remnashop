from datetime import timedelta

from redis.asyncio import Redis

from app.core.enums import Locale, Role
from app.core.utils.time import datetime_now
from app.modules.overview.online import record_online_sample
from app.modules.overview.usecases import GetHourlyOnlineUseCase
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
_KEYS = (
    "remnashop:remnawave:online:latest",
    "remnashop:remnawave:online:daily_peak",
    "remnashop:remnawave:online:hourly_peak",
)


async def test_returns_24_hours_ending_with_the_current_one(redis: Redis) -> None:
    await redis.delete(*_KEYS)
    now = datetime_now()
    await record_online_sample(redis, now - timedelta(hours=2), 40)
    await record_online_sample(redis, now, 15)

    result = await GetHourlyOnlineUseCase(redis)(OWNER)

    assert len(result.points) == 24
    assert result.points[-1].hour == now.replace(minute=0, second=0, microsecond=0)
    assert result.points[-1].peak == 15
    assert result.points[-3].peak == 40
    assert result.points[0].peak is None
    assert result.current == 15

    await redis.delete(*_KEYS)
