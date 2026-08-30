from app.core.exceptions import ConflictError, NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import SessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserDto, UserRepository


class ListUserSessionsUseCase(UseCase[int, list[SessionDto]]):
    required_permission = Permission.USER_SESSIONS_VIEW

    def __init__(
        self, session_repository: SessionRepository, user_repository: UserRepository
    ) -> None:
        self._session_repository = session_repository
        self._user_repository = user_repository

    async def _execute(self, actor: UserDto, data: int) -> list[SessionDto]:
        target = await self._user_repository.get_by_id(data)
        if target is None:
            raise NotFoundError("User not found")
        if target.role > actor.role:
            raise ConflictError("Cannot manage sessions for a higher-privileged account")

        return await self._session_repository.list_active_by_user(data)
