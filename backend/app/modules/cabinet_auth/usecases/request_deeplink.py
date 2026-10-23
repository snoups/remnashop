from typing import Optional

from app.core.constants import T_ME, TTL_5M, WEBAUTH_START_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import DeeplinkTicketDto, InviteCodesDto
from app.modules.oauth import new_binding
from app.modules.settings import SettingsRepository, fetch_bot_username


class RequestDeeplinkUseCase:
    def __init__(
        self, settings_repository: SettingsRepository, store: DeeplinkStore, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._uow = uow

    async def execute(
        self, codes: InviteCodesDto, link_user_id: Optional[int] = None
    ) -> DeeplinkTicketDto:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            bot = await self._settings_repository.get_bot_settings()
        if not cabinet.telegram_enabled or bot.token is None:
            raise AuthenticationError(
                "Telegram sign-in is disabled", code=ErrorCode.CABINET_TELEGRAM_DISABLED
            )
        username = await fetch_bot_username(bot.token.get_secret_value(), bot.proxy)
        if username is None:
            raise AuthenticationError(
                "The bot is unreachable", code=ErrorCode.OAUTH_PROVIDER_UNREACHABLE
            )
        # a sign-in link only works in the browser that asked for it, so a link
        # sent to someone else can't sign them into the sender's account; a link
        # to an account is already tied to that account's session
        binding, binding_hash = (None, None) if link_user_id is not None else new_binding()
        token = await self._store.create(codes, link_user_id, binding_hash)
        return DeeplinkTicketDto(
            bot_url=f"{T_ME}{username}?start={WEBAUTH_START_PREFIX}{token}",
            expires_in=TTL_5M,
            binding=binding,
        )
