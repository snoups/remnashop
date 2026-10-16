from typing import Optional

from app.core.constants import T_ME, TTL_5M, WEBAUTH_START_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import DeeplinkTicketDto, InviteCodesDto
from app.modules.settings import SettingsRepository, fetch_bot_username


class RequestDeeplinkUseCase:
    def __init__(
        self, settings_repository: SettingsRepository, store: DeeplinkStore, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._uow = uow

    async def execute(
        self, codes: InviteCodesDto, client_ip: str, user_agent: Optional[str]
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
        token = await self._store.create(codes, client_ip, user_agent)
        return DeeplinkTicketDto(
            bot_url=f"{T_ME}{username}?start={WEBAUTH_START_PREFIX}{token}",
            expires_in=TTL_5M,
        )
