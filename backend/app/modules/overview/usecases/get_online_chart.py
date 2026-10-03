from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.overview.dto import DailyCountDto, GetOverviewChartDto, OnlineChartDto
from app.modules.overview.online import read_daily_online_peaks, read_latest_online
from app.modules.overview.period import resolve_period
from app.modules.users import UserStatsRepository


class GetOnlineChartUseCase(UseCase[GetOverviewChartDto, OnlineChartDto]):
    # Remnawave's online count, shown to every admin like the rest of the overview
    required_permission = Permission.PUBLIC

    def __init__(self, user_stats: UserStatsRepository, redis: Redis, uow: UnitOfWork) -> None:
        self._user_stats = user_stats
        self._redis = redis
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetOverviewChartDto) -> OnlineChartDto:
        async with self._uow:
            period = await resolve_period(self._user_stats, data.days)
        peak_rows = await read_daily_online_peaks(self._redis, period.days())
        return OnlineChartDto(
            days=data.days,
            granularity=period.granularity,
            current=await read_latest_online(self._redis),
            daily_peak=[
                DailyCountDto(day=day, count=count)
                for day, count in period.bucketize(peak_rows, 0, op=max)
            ],
        )
