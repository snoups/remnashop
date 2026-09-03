from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistSourceDto, ToggleBlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository

if TYPE_CHECKING:
    # app.modules.users now imports BlacklistRepository (block/unblock usecases) --
    # an eager import here would cycle back into a partially-initialized
    # app.modules.users, same class of fix as core/usecase.py and core/events.py.
    from app.modules.users import UserDto


class ToggleBlacklistSourceUseCase(UseCase[ToggleBlacklistSourceDto, BlacklistSourceDto]):
    required_permission = Permission.BLACKLIST_SOURCE_TOGGLE

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ToggleBlacklistSourceDto) -> BlacklistSourceDto:
        async with self._uow:
            result = await self._blacklist_repository.set_source_enabled(
                data.source_id, data.enabled
            )
        if result is None:
            raise NotFoundError(f"Blacklist source not found: {data.source_id}")
        return result
