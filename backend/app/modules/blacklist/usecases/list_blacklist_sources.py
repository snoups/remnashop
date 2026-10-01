from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository

if TYPE_CHECKING:
    # app.modules.users now imports BlacklistRepository (block/unblock usecases) --
    # an eager import here would cycle back into a partially-initialized
    # app.modules.users, same class of fix as core/usecase.py and core/events.py.
    pass


class ListBlacklistSourcesUseCase(UseCase[None, list[BlacklistSourceDto]]):
    required_permission = Permission.BLACKLIST_SOURCES_VIEW

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[BlacklistSourceDto]:
        async with self._uow:
            return await self._blacklist_repository.list_sources()
