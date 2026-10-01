from dataclasses import dataclass

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.auth.events import UserSessionRevokedByAdminEvent
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserRepository


@dataclass(frozen=True, kw_only=True)
class RevokeUserSessionDto:
    user_id: int
    session_id: int
    client_ip: str


class RevokeUserSessionUseCase(UseCase[RevokeUserSessionDto, None]):
    required_permission = Permission.USER_SESSIONS_REVOKE

    def __init__(
        self,
        session_repository: SessionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._session_repository = session_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: RevokeUserSessionDto) -> None:
        async with self._uow:
            session = await self._session_repository.get_active_by_id(data.session_id)
            if session is None or session.user_id != data.user_id:
                raise NotFoundError("Session not found", code=ErrorCode.SESSION_NOT_FOUND)

            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            if not PermissionPolicy.can_manage(actor, target):
                raise ConflictError(
                    "Cannot manage sessions for an equally or more privileged account",
                    code=ErrorCode.SESSIONS_TARGET_TOO_PRIVILEGED,
                )

        async with self._uow:
            await self._session_repository.revoke_by_id(data.session_id)
            await self._event_publisher.publish(
                UserSessionRevokedByAdminEvent(
                    actor=actor,
                    target=target,
                    session_id=data.session_id,
                    ip_address=data.client_ip,
                )
            )
