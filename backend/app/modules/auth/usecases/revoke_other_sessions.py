from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import RevokeOtherSessionsDto
from app.modules.auth.events import OtherSessionsRevokedEvent
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserDto


class RevokeOtherSessionsUseCase(UseCase[RevokeOtherSessionsDto, None, UserDto]):
    """Ends every dashboard session of the actor except the one the request came from."""

    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        session_repository: SessionRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._session_repository = session_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: RevokeOtherSessionsDto) -> None:
        async with self._uow:
            await self._session_repository.revoke_all_by_user(
                actor.id,
                keep_session_id=data.current_session_id,
                audience=SessionAudience.DASHBOARD,
            )
            await self._event_publisher.publish(
                OtherSessionsRevokedEvent(
                    user=actor,
                    kept_session_id=data.current_session_id,
                    ip_address=data.client_ip,
                )
            )
