from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.utils.email import normalize_email
from app.modules.cabinet_auth import (
    InviteCodesDto,
    email_key,
    fail_budget_exhausted,
    send_limit_hit,
)
from app.modules.email import SendEmailDispatch, load_email_brand, render_link_code
from app.modules.identity_links.email_codes import LinkEmailCodeStore
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class RequestLinkEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: LinkEmailCodeStore,
        send_email: SendEmailDispatch,
        redis: Redis,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._send_email = send_email
        self._redis = redis
        self._config = config
        self._uow = uow

    async def execute(self, user: UserDto, email: str, locale: Locale) -> None:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            email_settings = await self._settings_repository.get_email_settings()
            brand = await load_email_brand(self._settings_repository)
        if not (cabinet.email_enabled and email_settings.is_configured):
            raise AuthenticationError(
                "Email sign-in is disabled", code=ErrorCode.CABINET_EMAIL_DISABLED
            )

        # over a limit the answer stays 204, so the limits don't reveal anything
        digest = email_key(email)
        if await fail_budget_exhausted(self._redis, digest) or await send_limit_hit(
            self._redis, digest
        ):
            return

        code = await self._store.issue(email, InviteCodesDto(), locale)
        subject, text, html = render_link_code(
            code, locale, brand, self._config.cabinet.url or None
        )
        await self._send_email.kiq(to=normalize_email(email), subject=subject, text=text, html=html)
