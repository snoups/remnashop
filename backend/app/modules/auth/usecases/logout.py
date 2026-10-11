from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.security import hash_refresh_token
from app.modules.auth.repository import SessionRepository


class LogoutUseCase:
    def __init__(self, session_repository: SessionRepository, uow: UnitOfWork) -> None:
        self._session_repository = session_repository
        self._uow = uow

    async def execute(
        self, refresh_token: str, audience: SessionAudience = SessionAudience.DASHBOARD
    ) -> None:
        async with self._uow:
            session = await self._session_repository.get_rotatable_by_hash(
                hash_refresh_token(refresh_token)
            )
        if session is not None and session.audience is audience:
            async with self._uow:
                await self._session_repository.revoke_by_id(session.id)
