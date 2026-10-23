from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import RevokeUserSessionDto
from app.modules.auth.events import UserSessionRevokedByAdminEvent
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserRepository, assert_manageable, get_visible_target


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
            session = await self._session_repository.find_active_by_id(data.session_id)
            if session is None or session.user_id != data.user_id:
                raise NotFoundError("Session not found", code=ErrorCode.SESSION_NOT_FOUND)

            target = await get_visible_target(self._user_repository, actor, data.user_id)
            assert_manageable(actor, target)

            await self._session_repository.revoke_by_id(data.session_id)
            await self._event_publisher.publish(
                UserSessionRevokedByAdminEvent(
                    actor=actor,
                    target=target,
                    session_id=data.session_id,
                    ip_address=data.client_ip,
                )
            )
