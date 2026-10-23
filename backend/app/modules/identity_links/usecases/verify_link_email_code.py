from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.cabinet_auth import (
    email_key,
    require_email_sign_in,
    verify_email_code,
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
            await require_email_sign_in(self._settings_repository)
        await verify_email_code(
            self._store,
            self._redis,
            self._event_publisher,
            self._uow,
            email,
            code,
            client_ip,
            budget=link_fail_key(user.id, email_key(email)),
        )
        return await self._linker.link(
            user, IdentityClaimDto(kind=IdentityKind.EMAIL, email=email), client_ip
        )
