from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository

if TYPE_CHECKING:
    # app.modules.users now imports BlacklistRepository (block/unblock usecases) --
    # an eager import here would cycle back into a partially-initialized
    # app.modules.users, same class of fix as core/usecase.py and core/events.py.
    from app.modules.users import UserDto


class ListBlacklistSourcesUseCase(UseCase[None, list[BlacklistSourceDto]]):
    required_permission = Permission.BLACKLIST_SOURCES_VIEW

    def __init__(self, blacklist_repository: BlacklistRepository) -> None:
        self._blacklist_repository = blacklist_repository

    async def _execute(self, actor: UserDto, data: None) -> list[BlacklistSourceDto]:
        return await self._blacklist_repository.list_sources()
