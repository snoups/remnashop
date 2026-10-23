from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.modules.cabinet_auth import (
    EmailCodeAttemptsExhausted,
    EmailCodeAttemptsExhaustedEvent,
    EmailCodeExpired,
    email_key,
    release_attempt,
    reserve_attempt,
)
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind, LinkResultDto
from app.modules.identity_links.email_codes import LinkEmailCodeStore, link_fail_key
from app.modules.identity_links.linker import IdentityLinker
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class VerifyLinkEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: LinkEmailCodeStore,
        redis: Redis,
        linker: IdentityLinker,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._redis = redis
        self._linker = linker
        self._event_publisher = event_publisher
        self._uow = uow

    async def execute(self, user: UserDto, email: str, code: str, client_ip: str) -> LinkResultDto:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            email_settings = await self._settings_repository.get_email_settings()
        if not (cabinet.email_enabled and email_settings.is_configured):
            raise AuthenticationError(
                "Email sign-in is disabled", code=ErrorCode.CABINET_EMAIL_DISABLED
            )
        digest = email_key(email)
        budget = link_fail_key(user.id, digest)
        if not await reserve_attempt(self._redis, budget):
            raise AuthenticationError("The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED)
        try:
            grant = await self._store.verify(email, code)
        except EmailCodeExpired:
            await release_attempt(self._redis, budget)
            raise AuthenticationError(
                "The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED
            ) from None
        except EmailCodeAttemptsExhausted:
            async with self._uow:
                await self._event_publisher.publish(
                    EmailCodeAttemptsExhaustedEvent(email_hash=digest, ip_address=client_ip)
                )
            raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID) from None
        if grant is None:
            raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID)
        await release_attempt(self._redis, budget)
        return await self._linker.link(
            user, IdentityClaimDto(kind=IdentityKind.EMAIL, email=email), client_ip
        )
