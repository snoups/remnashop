from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import SessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserRepository, assert_manageable, get_visible_target


class ListUserSessionsUseCase(UseCase[int, list[SessionDto]]):
    required_permission = Permission.USER_SESSIONS_VIEW

    def __init__(
        self,
        session_repository: SessionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._session_repository = session_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> list[SessionDto]:
        async with self._uow:
            target = await get_visible_target(self._user_repository, actor, data)
            assert_manageable(actor, target)

            return await self._session_repository.list_active_by_user(data)
