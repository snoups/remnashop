from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import SessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserDto


class ListSessionsUseCase(UseCase[None, list[SessionDto]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    async def _execute(self, actor: UserDto, data: None) -> list[SessionDto]:
        return await self._session_repository.list_active_by_user(actor.id)
