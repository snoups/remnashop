from datetime import timedelta
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.users.dto import GetUserListStatsDto, UserListStatsDto
from app.modules.users.listing import resolve_list_roles
from app.modules.users.stats_repository import UserStatsRepository

TOTAL_GROWTH_WINDOW: Final[timedelta] = timedelta(days=30)


class GetUserListStatsUseCase(UseCase[GetUserListStatsDto, UserListStatsDto]):
    required_permission = Permission.USERS_STATS_VIEW

    def __init__(self, user_stats: UserStatsRepository, uow: UnitOfWork) -> None:
        self._user_stats = user_stats
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetUserListStatsDto) -> UserListStatsDto:
        now = datetime_now()
        async with self._uow:
            return await self._user_stats.list_stats(
                roles=resolve_list_roles(actor, data.include_staff),
                growth_since=now - TOTAL_GROWTH_WINDOW,
            )
