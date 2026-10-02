from typing import Final, Optional

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import T_ME
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkShareUrlsDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.settings import SettingsRepository, fetch_bot_username

# matches telegram/middlewares/_codes.py's _AD_LINK_PREFIX
_BOT_START_QUERY: Final[str] = "?start=ad_{code}"
_WEBCABINET_QUERY: Final[str] = "?ad={code}"


class GetAdLinkShareUrlsUseCase(UseCase[int, AdLinkShareUrlsDto]):
    required_permission = Permission.AD_LINKS_SHARE_VIEW

    def __init__(
        self,
        ad_link_repository: AdLinkRepository,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> AdLinkShareUrlsDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.get_by_id(data)
            bot_settings = await self._settings_repository.get_bot_settings()

        bot_url: Optional[str] = None
        if ad_link.allow_bot and bot_settings.is_configured and bot_settings.token is not None:
            username = await fetch_bot_username(
                bot_settings.token.get_secret_value(), bot_settings.proxy
            )
            if username:
                bot_url = f"{T_ME}{username}{_BOT_START_QUERY.format(code=ad_link.code)}"

        webcabinet_url: Optional[str] = None
        cabinet_url = self._config.web_cabinet_url.strip().rstrip("/")
        if ad_link.allow_webcabinet and cabinet_url:
            webcabinet_url = f"{cabinet_url}/{_WEBCABINET_QUERY.format(code=ad_link.code)}"

        return AdLinkShareUrlsDto(bot_url=bot_url, webcabinet_url=webcabinet_url)
