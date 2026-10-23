from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.utils.email import normalize_email
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth import (
    InviteCodesDto,
    email_key,
    fail_budget_exhausted,
    is_allowed_domain,
    require_email_sign_in,
    send_limit_hit,
)
from app.modules.email import SendEmailDispatch, load_email_brand, render_link_code
from app.modules.identity_links.email_codes import LinkEmailCodeStore, link_fail_key
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


class RequestLinkEmailCodeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: LinkEmailCodeStore,
        send_email: SendEmailDispatch,
        redis: Redis,
        config: AppConfig,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._send_email = send_email
        self._redis = redis
        self._config = config
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def execute(self, user: UserDto, email: str, locale: Locale) -> None:
        async with self._uow:
            cabinet = await require_email_sign_in(self._settings_repository)
            brand = await load_email_brand(self._settings_repository)

        digest = email_key(email)
        # the account's own email slot is taken: the link would be refused anyway
        if user.email is not None and email_key(user.email) != digest:
            raise ConflictError(
                "A different 'email' is already linked", code=ErrorCode.MERGE_IDENTITY_CONFLICT
            )
        async with self._uow:
            owner = await self._user_repository.find_by_email(email)
            # a new address must pass what attaching it checks; refused silently,
            # since an error here would tell a free address from a taken one
            if owner is None and (
                not is_allowed_domain(email, cabinet)
                or await self._blacklist_repository.is_blacklisted_email(email)
            ):
                return

        # over a limit the answer stays 204, so the limits don't reveal anything
        if await fail_budget_exhausted(
            self._redis, link_fail_key(user.id, digest)
        ) or await send_limit_hit(self._redis, digest):
            return

        code = await self._store.issue(email, InviteCodesDto(), locale)
        subject, text, html = render_link_code(
            code, locale, brand, self._config.cabinet.url or None
        )
        # an address that canonically belongs to another account gets proven at
        # that account's own mailbox, as sign-in does: an alias the claimant owns
        # (a "+" that is part of the name on some hosts) must not stand in for it
        recipient = owner.email if owner is not None and owner.email else email
        await self._send_email.kiq(
            to=normalize_email(recipient), subject=subject, text=text, html=html
        )
