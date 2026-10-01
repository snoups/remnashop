from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.command_translations import repush_bot_commands_if_configured
from app.modules.settings.events import LocaleActivatedEvent
from app.modules.settings.repository import SettingsRepository
from app.modules.translations import TranslationsRepository


class AddLocaleUseCase(UseCase[Locale, list[Locale]]):
    required_permission = Permission.LOCALES_ADD

    def __init__(
        self,
        settings_repository: SettingsRepository,
        translations_repository: TranslationsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        config: AppConfig,
    ) -> None:
        self._settings_repository = settings_repository
        self._translations_repository = translations_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._config = config

    async def _execute(self, actor: Actor, data: Locale) -> list[Locale]:
        async with self._uow:
            # PUT semantics: re-adding is a no-op, not a re-copy over edited translations
            locales = await self._settings_repository.list_active_locales()
            if data in locales:
                return locales
            await self._settings_repository.add_active_locale(data)
            # In the same transaction, not a worker task: the dashboard
            # re-reads the translations right after this returns, and an
            # async copy loses that race -- the new locale reads as empty.
            await self._translations_repository.copy_locale_from(Locale.EN, data)
            locales = await self._settings_repository.list_active_locales()
            await self._event_publisher.publish(LocaleActivatedEvent(actor=actor, locale=data))
        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config, self._uow
        )
        return locales
