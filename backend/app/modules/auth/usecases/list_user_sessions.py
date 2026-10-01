from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.auth.dto import SessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserRepository


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
            target = await self._user_repository.get_by_id(data)
            if target is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            if not PermissionPolicy.can_manage(actor, target):
                raise ConflictError(
                    "Cannot manage sessions for an equally or more privileged account",
                    code=ErrorCode.SESSIONS_TARGET_TOO_PRIVILEGED,
                )

            return await self._session_repository.list_active_by_user(data)
