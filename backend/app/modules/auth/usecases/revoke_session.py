from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.events import SessionRevokedEvent
from app.modules.auth.repository import SessionRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class RevokeSessionDto:
    session_id: int
    client_ip: str


class RevokeSessionUseCase(UseCase[RevokeSessionDto, None]):
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

    async def _execute(self, actor: UserDto, data: RevokeSessionDto) -> None:
        session = await self._session_repository.get_active_by_id(data.session_id)
        if session is None or session.user_id != actor.id:
            # Same message whether it doesn't exist or belongs to someone else --
            # don't leak which case it was.
            raise NotFoundError("Session not found")

        async with self._uow:
            await self._session_repository.revoke_by_id(data.session_id)
            await self._event_publisher.publish(
                SessionRevokedEvent(
                    user=actor, session_id=data.session_id, ip_address=data.client_ip
                )
            )
