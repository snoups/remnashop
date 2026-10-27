from typing import Optional

from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.utils.email import normalize_email
from app.modules.cabinet_auth.captcha import verify_captcha
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.email_codes import (
    EmailCodeStore,
    email_key,
    fail_budget_exhausted,
    require_email_sign_in,
    send_limit_hit,
)
from app.modules.cabinet_auth.email_domains import is_allowed_domain
from app.modules.email import SendEmailDispatch, load_email_brand, render_login_code
from app.modules.settings import SettingsRepository
from app.modules.users import UserRepository


class RequestEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: EmailCodeStore,
        send_email: SendEmailDispatch,
        redis: Redis,
        config: AppConfig,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._send_email = send_email
        self._redis = redis
        self._config = config
        self._user_repository = user_repository
        self._uow = uow

    async def execute(
        self,
        email: str,
        locale: Locale,
        codes: InviteCodesDto,
        captcha_token: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        async with self._uow:
            cabinet = await require_email_sign_in(self._settings_repository)
            brand = await load_email_brand(self._settings_repository)
        await verify_captcha(cabinet, captcha_token, client_ip)

        async with self._uow:
            existing = await self._user_repository.find_by_email(email)
        if existing is None and not is_allowed_domain(email, cabinet):
            return

        # over a limit the answer stays 204, so the limits don't reveal anything
        digest = email_key(email)
        if await fail_budget_exhausted(self._redis, digest):
            return
        if await send_limit_hit(self._redis, digest):
            return

        code = await self._store.issue(email, codes, locale)
        subject, text, html = render_login_code(
            code, locale, brand, self._config.cabinet.url or None
        )
        recipient = existing.email if existing is not None and existing.email else email
        await self._send_email.kiq(
            to=normalize_email(recipient), subject=subject, text=text, html=html
        )
