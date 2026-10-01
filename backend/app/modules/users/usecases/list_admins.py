from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository


class ListAdminsUseCase(UseCase[None, list[UserDto]]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[UserDto]:
        async with self._uow:
            return await self._user_repository.list_by_roles([Role.OWNER, Role.ADMIN])
