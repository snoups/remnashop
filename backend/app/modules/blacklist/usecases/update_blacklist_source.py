from __future__ import annotations

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistSourceDto, UpdateBlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository


class UpdateBlacklistSourceUseCase(UseCase[UpdateBlacklistSourceDto, BlacklistSourceDto]):
    required_permission = Permission.BLACKLIST_SOURCE_UPDATE

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateBlacklistSourceDto) -> BlacklistSourceDto:
        async with self._uow:
            result = await self._blacklist_repository.set_source_enabled(
                data.source_id, data.enabled
            )
        if result is None:
            raise NotFoundError(
                f"Blacklist source not found: {data.source_id}",
                code=ErrorCode.BLACKLIST_SOURCE_NOT_FOUND,
            )
        return result
