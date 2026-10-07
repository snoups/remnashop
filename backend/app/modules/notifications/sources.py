from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.modules.notifications.render import NotificationRenderer
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationRepository


class BotTokenSource:
    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def get_bot_token(self) -> tuple[Optional[str], Optional[str]]:
        async with self._uow:
            settings = await self._settings_repository.get_bot_settings()
        token = settings.token.get_secret_value() if settings.token is not None else None
        return token, settings.proxy


class NotificationRendererFactory:
    def __init__(
        self, translation_repository: TranslationRepository, uow: UnitOfWork, config: AppConfig
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._config = config

    async def build(self) -> NotificationRenderer:
        async with self._uow:
            locales = await self._translation_repository.list_active_locales()
            texts = await self._translation_repository.get_fluent_text_by_locale(locales)
        return NotificationRenderer(texts, default_locale=self._config.default_locale)
