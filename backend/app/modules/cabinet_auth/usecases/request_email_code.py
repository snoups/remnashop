from typing import Final

from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX, TIME_1M
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.utils.email import normalize_email
from app.core.utils.rate_counter import hit_counter
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.email_codes import EmailCodeStore, email_key, fail_budget_exhausted
from app.modules.email import SendEmailDispatch, load_email_brand, render_login_code
from app.modules.settings import SettingsRepository

_LIMIT_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code_limit:"
_HOUR: Final[int] = TIME_1M * 60
_PER_HOUR: Final[int] = 10


class RequestEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: EmailCodeStore,
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

    async def execute(self, email: str, locale: Locale, codes: InviteCodesDto) -> None:
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
        if await fail_budget_exhausted(self._redis, digest):
            return
        if await hit_counter(self._redis, f"{_LIMIT_PREFIX}min:{digest}", TIME_1M) > 1:
            return
        if await hit_counter(self._redis, f"{_LIMIT_PREFIX}hour:{digest}", _HOUR) > _PER_HOUR:
            return

        code = await self._store.issue(email, codes, locale)
        subject, text, html = render_login_code(
            code, locale, brand, self._config.web_cabinet_url.strip() or None
        )
        await self._send_email.kiq(to=normalize_email(email), subject=subject, text=text, html=html)
