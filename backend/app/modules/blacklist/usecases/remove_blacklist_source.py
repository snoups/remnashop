from __future__ import annotations

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.repository import BlacklistRepository


class RemoveBlacklistSourceUseCase(UseCase[int, None]):
    required_permission = Permission.BLACKLIST_SOURCE_REMOVE

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._blacklist_repository.remove_source(data)
