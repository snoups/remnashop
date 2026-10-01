from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.users.dto import UserListStatsDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.list_users import resolve_list_roles

NEW_USERS_WINDOW: Final[timedelta] = timedelta(days=7)
TOTAL_GROWTH_WINDOW: Final[timedelta] = timedelta(days=30)


@dataclass(frozen=True, kw_only=True)
class GetUserListStatsInput:
    include_staff: bool = False


class GetUserListStatsUseCase(UseCase[GetUserListStatsInput, UserListStatsDto]):
    required_permission = Permission.USERS_STATS_VIEW

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetUserListStatsInput) -> UserListStatsDto:
        now = datetime_now()
        async with self._uow:
            return await self._user_repository.list_stats(
                roles=resolve_list_roles(actor, data.include_staff),
                new_since=now - NEW_USERS_WINDOW,
                previous_since=now - 2 * NEW_USERS_WINDOW,
                growth_since=now - TOTAL_GROWTH_WINDOW,
            )
