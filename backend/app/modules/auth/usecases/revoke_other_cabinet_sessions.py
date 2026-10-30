from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserDto


class RevokeOtherCabinetSessionsUseCase(UseCase[int, None, UserDto]):
    """Ends every cabinet session of the actor except the one the request came from."""

    required_permission = Permission.PUBLIC

    def __init__(self, session_repository: SessionRepository, uow: UnitOfWork) -> None:
        self._session_repository = session_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, current_session_id: int) -> None:
        async with self._uow:
            await self._session_repository.revoke_all_by_user(
                actor.id, keep_session_id=current_session_id, audience=SessionAudience.CABINET
            )
