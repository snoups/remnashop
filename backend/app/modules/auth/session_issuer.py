from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import AppConfig
from app.core.constants import TTL_30D
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    derive_csrf_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository


@dataclass(frozen=True, kw_only=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_at: datetime


class SessionIssuer:
    def __init__(
        self, session_repository: SessionRepository, uow: UnitOfWork, config: AppConfig
    ) -> None:
        self._session_repository = session_repository
        self._uow = uow
        self._config = config

    async def issue(
        self,
        user_id: int,
        ip_address: str,
        user_agent: Optional[str],
        audience: SessionAudience = SessionAudience.DASHBOARD,
        ttl_seconds: int = TTL_30D,
    ) -> IssuedSession:
        refresh_token = generate_refresh_token()
        expires_at = datetime_now() + timedelta(seconds=ttl_seconds)

        async with self._uow:
            await self._session_repository.revoke_active_by_fingerprint(
                user_id, ip_address, user_agent, audience
            )
            session = await self._session_repository.create(
                CreateSessionDto(
                    user_id=user_id,
                    refresh_token_hash=hash_refresh_token(refresh_token),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    expires_at=expires_at,
                    audience=audience,
                )
            )

        secret = self._config.jwt_secret.get_secret_value()
        access_token = create_access_token(user_id, session.id, secret)
        csrf_token = derive_csrf_token(refresh_token, secret)

        return IssuedSession(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    def generate_new_refresh_token(self) -> str:
        return generate_refresh_token()

    async def reissue_access_only(
        self, user_id: int, session_id: int, refresh_token: str
    ) -> IssuedSession:
        # for RefreshSessionUseCase after it rotated the row: mints the
        # access/csrf pair for an existing session instead of creating one
        session = await self._session_repository.get_active_by_id(session_id)
        if session is None:
            # revoked between the rotation and this read
            raise AuthenticationError(
                "Invalid or expired refresh token", code=ErrorCode.REFRESH_TOKEN_INVALID
            )
        secret = self._config.jwt_secret.get_secret_value()
        access_token = create_access_token(user_id, session_id, secret)
        csrf_token = derive_csrf_token(refresh_token, secret)
        return IssuedSession(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            expires_at=session.expires_at,
        )
