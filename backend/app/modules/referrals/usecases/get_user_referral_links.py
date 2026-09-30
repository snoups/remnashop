from typing import Final, Optional

from app.core.config import AppConfig
from app.core.constants import T_ME
from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralLinksDto
from app.modules.settings import SettingsRepository, fetch_bot_username
from app.modules.users import UserDto, UserRepository

# matches telegram/middlewares/_codes.py's _REFERRAL_PREFIX
_BOT_START_QUERY: Final[str] = "?start=ref_{code}"
_WEBCABINET_QUERY: Final[str] = "?ref={code}"


class GetUserReferralLinksUseCase(UseCase[int, ReferralLinksDto]):
    required_permission = Permission.REFERRALS_LINKS_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> ReferralLinksDto:
        async with self._uow:
            user = await self._user_repository.get_by_id(data)
            if user is None:
                raise NotFoundError(f"User '{data}' not found")
            bot_settings = await self._settings_repository.get_bot_settings()

        code = user.referral_code
        if not code:
            return ReferralLinksDto()

        bot_url: Optional[str] = None
        if bot_settings.is_configured and bot_settings.token is not None:
            username = await fetch_bot_username(bot_settings.token.get_secret_value())
            if username:
                bot_url = f"{T_ME}{username}{_BOT_START_QUERY.format(code=code)}"

        webcabinet_url: Optional[str] = None
        cabinet_url = self._config.web_cabinet_url.strip().rstrip("/")
        if cabinet_url:
            webcabinet_url = f"{cabinet_url}/{_WEBCABINET_QUERY.format(code=code)}"

        return ReferralLinksDto(bot_url=bot_url, webcabinet_url=webcabinet_url)
