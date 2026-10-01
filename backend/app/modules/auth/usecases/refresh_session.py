from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.core.security import hash_refresh_token
from app.modules.auth.events import SessionTheftDetectedEvent
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import IssuedSession, SessionIssuer


class RefreshSessionUseCase:
    def __init__(
        self,
        session_repository: SessionRepository,
        session_issuer: SessionIssuer,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._session_repository = session_repository
        self._session_issuer = session_issuer
        self._uow = uow
        self._event_publisher = event_publisher

    async def execute(
        self, refresh_token: str, ip_address: str, user_agent: Optional[str]
    ) -> IssuedSession:
        async with self._uow:
            presented_hash = hash_refresh_token(refresh_token)

            current_session = await self._session_repository.get_by_current_hash(presented_hash)
        if current_session is not None:
            new_refresh_token = self._session_issuer.generate_new_refresh_token()
            async with self._uow:
                await self._session_repository.rotate(
                    current_session.id,
                    hash_refresh_token(new_refresh_token),
                    extend_grace=True,
                )
            return await self._session_issuer.reissue_access_only(
                current_session.user_id, current_session.id, new_refresh_token
            )

        async with self._uow:
            graced_session = await self._session_repository.get_by_previous_hash_in_grace(
                presented_hash
            )
        if graced_session is not None:
            new_refresh_token = self._session_issuer.generate_new_refresh_token()
            async with self._uow:
                await self._session_repository.rotate(
                    graced_session.id,
                    hash_refresh_token(new_refresh_token),
                    extend_grace=False,
                )
            return await self._session_issuer.reissue_access_only(
                graced_session.user_id, graced_session.id, new_refresh_token
            )

        async with self._uow:
            theft_session = await self._session_repository.get_by_expired_previous_hash(
                presented_hash
            )
        if theft_session is not None:
            async with self._uow:
                await self._session_repository.revoke_by_id(theft_session.id)
                await self._event_publisher.publish(
                    SessionTheftDetectedEvent(
                        user_id=theft_session.user_id,
                        session_id=theft_session.id,
                        ip_address=ip_address,
                    )
                )

        raise AuthenticationError(
            "Invalid or expired refresh token", code=ErrorCode.REFRESH_TOKEN_INVALID
        )
