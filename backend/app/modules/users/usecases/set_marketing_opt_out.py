from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository


class SetMarketingOptOutUseCase(UseCase[bool, None, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: bool) -> None:
        async with self._uow:
            await self._user_repository.set_marketing_opt_out(actor.id, data)
        logger.info(f"{actor.log} Set marketing opt-out to {data}")
