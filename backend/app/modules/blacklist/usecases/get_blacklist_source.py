from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist.dto import BlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository


class GetBlacklistSourceUseCase(UseCase[int, BlacklistSourceDto]):
    required_permission = Permission.BLACKLIST_SOURCE_DETAIL_VIEW

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> BlacklistSourceDto:
        async with self._uow:
            source = await self._blacklist_repository.get_source(data)
        if source is None:
            raise NotFoundError(
                f"Blacklist source not found: {data}", code=ErrorCode.BLACKLIST_SOURCE_NOT_FOUND
            )
        return source
