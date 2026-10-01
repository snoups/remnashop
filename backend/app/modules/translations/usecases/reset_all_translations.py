from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository, repush_bot_commands_if_configured
from app.modules.translations.publish import publish_translation_change
from app.modules.translations.repository import TranslationsRepository


class ResetAllTranslationsUseCase(UseCase[None, None]):
    required_permission = Permission.TRANSLATIONS_RESET_ALL

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        config: AppConfig,
        redis: Redis,
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config
        self._redis = redis

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            locales = await self._settings_repository.list_active_locales()
            for locale in locales:
                await self._translations_repository.reset_locale(locale)
            reset = [
                entry
                for locale in locales
                for entry in await self._translations_repository.list_by_locale(locale)
            ]

        for entry in reset:
            await publish_translation_change(
                self._redis,
                entry.locale,
                entry.message_id,
                entry.value,
                attribute_id=entry.attribute_id,
            )

        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config, self._uow
        )
