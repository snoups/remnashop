from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.cabinet_auth.dto import CabinetMethodsDto, CaptchaWidgetDto
from app.modules.settings import SettingsRepository


class GetCabinetMethodsUseCase:
    def __init__(
        self, settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def execute(self) -> CabinetMethodsDto:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            bot = await self._settings_repository.get_bot_settings()
            oauth = await self._settings_repository.get_oauth_settings()
            email = await self._settings_repository.get_email_settings()
        telegram = cabinet.telegram_enabled and bot.is_configured
        providers: list[OAuthProvider] = []
        # authorize needs the cabinet URL for its redirect
        has_cabinet_url = bool(self._config.cabinet.url)
        if has_cabinet_url and cabinet.telegram_oauth_enabled and oauth.is_telegram_configured:
            providers.append(OAuthProvider.TELEGRAM)
        if has_cabinet_url and cabinet.google_enabled and oauth.is_google_configured:
            providers.append(OAuthProvider.GOOGLE)
        if has_cabinet_url and cabinet.yandex_enabled and oauth.is_yandex_configured:
            providers.append(OAuthProvider.YANDEX)
        return CabinetMethodsDto(
            telegram_webapp=telegram,
            telegram_deeplink=telegram,
            email=cabinet.email_enabled and email.is_configured,
            oauth=providers,
            allowed_email_domains=(
                cabinet.allowed_email_domains if cabinet.restrict_email_domains else None
            ),
            captcha=(
                CaptchaWidgetDto(
                    provider=cabinet.captcha_provider, site_key=cabinet.captcha_site_key
                )
                if cabinet.captcha_enabled and cabinet.captcha_site_key is not None
                else None
            ),
        )
