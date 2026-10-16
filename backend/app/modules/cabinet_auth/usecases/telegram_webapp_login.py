import time
from typing import Optional

from app.core.constants import TTL_7D
from app.core.db.uow import UnitOfWork
from app.core.enums import RegistrationSource
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.init_data import codes_from_start_param, verify_init_data
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class TelegramWebAppLoginUseCase:
    def __init__(
        self, settings_repository: SettingsRepository, sign_in: CabinetSignIn, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._sign_in = sign_in
        self._uow = uow

    async def execute(
        self, init_data: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            bot = await self._settings_repository.get_bot_settings()
        if not cabinet.telegram_enabled or bot.token is None:
            raise AuthenticationError(
                "Telegram sign-in is disabled", code=ErrorCode.CABINET_TELEGRAM_DISABLED
            )
        data = verify_init_data(init_data, bot.token.get_secret_value(), int(time.time()))
        return await self._sign_in.telegram(
            data.profile,
            codes_from_start_param(data.start_param),
            client_ip,
            user_agent,
            # the Mini App signs in again with initData whenever its access token
            # expires, so a session left behind by an IP change needn't outlive a week
            session_ttl=TTL_7D,
            source=RegistrationSource.CABINET_MINI_APP,
        )
