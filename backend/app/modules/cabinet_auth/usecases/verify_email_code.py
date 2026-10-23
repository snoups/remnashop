from typing import Optional

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.email_codes import (
    EmailCodeStore,
    require_email_sign_in,
    verify_email_code,
)
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
        self,
        email: str,
        code: str,
        client_ip: str,
        user_agent: Optional[str],
        legal_locale: Optional[Locale] = None,
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            await require_email_sign_in(self._settings_repository)
        grant = await verify_email_code(
            self._store, self._redis, self._event_publisher, self._uow, email, code, client_ip
        )
        return await self._sign_in.email(
            email, grant.locale, grant.codes, client_ip, user_agent, legal_locale
        )
