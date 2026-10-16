from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class BotSignInUseCase:
    """The cabinet's side: trades the token from the bot's button for a session."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: DeeplinkStore,
        sign_in: CabinetSignIn,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._sign_in = sign_in
        self._uow = uow

    async def execute(
        self, token: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
        if not cabinet.telegram_enabled:
            raise AuthenticationError(
                "Telegram sign-in is disabled", code=ErrorCode.CABINET_TELEGRAM_DISABLED
            )
        grant = await self._store.take_signin(token)
        if grant is None:
            raise AuthenticationError(
                "The sign-in link has expired", code=ErrorCode.DEEPLINK_EXPIRED
            )
        return await self._sign_in.telegram(grant.profile, grant.codes, client_ip, user_agent)
