from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserListItemDto
from app.modules.users.listing import detail_roles
from app.modules.users.repository import UserRepository


class GetUserUseCase(UseCase[int, UserListItemDto]):
    required_permission = Permission.USERS_DETAIL_VIEW

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> UserListItemDto:
        # same staff visibility as ListUsersUseCase; deleted accounts stay
        # reachable since history still points at them
        async with self._uow:
            return await self._user_repository.get_list_item(data, detail_roles(actor))
