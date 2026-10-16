from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserRegistrationDto
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import get_visible_target


class GetUserRegistrationUseCase(UseCase[int, Optional[UserRegistrationDto]]):
    required_permission = Permission.USERS_REGISTRATION_VIEW

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> Optional[UserRegistrationDto]:
        async with self._uow:
            target = await get_visible_target(self._user_repository, actor, data)
            # None: signed up before snapshots were kept
            return await self._user_repository.find_registration(target.id)
