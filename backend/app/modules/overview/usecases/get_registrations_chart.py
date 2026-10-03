from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.overview.dto import DailyCountDto, GetOverviewChartDto, RegistrationsChartDto
from app.modules.overview.period import resolve_period
from app.modules.users import UserStatsRepository


class GetRegistrationsChartUseCase(UseCase[GetOverviewChartDto, RegistrationsChartDto]):
    # gated inside by the section's own read permission, like GetOverviewUseCase
    required_permission = Permission.PUBLIC

    def __init__(self, user_stats: UserStatsRepository, uow: UnitOfWork) -> None:
        self._user_stats = user_stats
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetOverviewChartDto) -> RegistrationsChartDto:
        if Permission.USERS_VIEW not in PermissionPolicy.effective_permissions(actor):
            raise PermissionDeniedError
        async with self._uow:
            period = await resolve_period(self._user_stats, data.days)
            daily = await self._user_stats.count_registrations_by_day(period.since, Role.USER)
        return RegistrationsChartDto(
            days=data.days,
            granularity=period.granularity,
            daily=[
                DailyCountDto(day=day, count=count) for day, count in period.bucketize(daily, 0)
            ],
        )
