from typing import Optional

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.email_codes import (
    EmailCodeAttemptsExhausted,
    EmailCodeExpired,
    EmailCodeStore,
    email_key,
    fail_budget_exhausted,
    record_failure,
)
from app.modules.cabinet_auth.events import EmailCodeAttemptsExhaustedEvent
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class VerifyEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: EmailCodeStore,
        redis: Redis,
        sign_in: CabinetSignIn,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._redis = redis
        self._sign_in = sign_in
        self._event_publisher = event_publisher
        self._uow = uow

    async def execute(
        self, email: str, code: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            email_settings = await self._settings_repository.get_email_settings()
        if not (cabinet.email_enabled and email_settings.is_configured):
            raise AuthenticationError(
                "Email sign-in is disabled", code=ErrorCode.CABINET_EMAIL_DISABLED
            )
        digest = email_key(email)
        if await fail_budget_exhausted(self._redis, digest):
            raise AuthenticationError("The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED)
        try:
            grant = await self._store.verify(email, code)
        except EmailCodeExpired:
            raise AuthenticationError(
                "The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED
            ) from None
        except EmailCodeAttemptsExhausted:
            await record_failure(self._redis, digest)
            async with self._uow:
                await self._event_publisher.publish(
                    EmailCodeAttemptsExhaustedEvent(email_hash=digest, ip_address=client_ip)
                )
            raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID) from None
        if grant is None:
            await record_failure(self._redis, digest)
            raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID)
        return await self._sign_in.email(email, grant.locale, grant.codes, client_ip, user_agent)
